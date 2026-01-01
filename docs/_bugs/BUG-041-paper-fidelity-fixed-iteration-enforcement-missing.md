# BUG-041: Paper-Fidelity Gap — Fixed Iteration Enforcement Missing (Early Answer Allowed)

## Severity: P1 (High) — Benchmark Validity / Paper Reproducibility

## Status: OPEN (2026-01-01)

## Summary

The GIANT paper’s reported results assume **fixed-iteration runs** where the model is **forced to provide its final response after a specific number of iterations** (e.g., `T=20`), with a “3 retries then incorrect” rule when the model violates the step limit.

Our current implementation does **not** enforce this contract:
- Prompts explicitly allow answering early.
- The agent accepts an `answer` action at any step and stops the loop.

This creates a **paper comparability failure**: runs configured with `max_steps=20` frequently use far fewer than 20 steps, which can materially change performance (and is likely to depress accuracy on harder tasks where the paper reports gains up to 20 iterations).

---

## Paper Requirement (Source of Truth)

The paper explicitly describes fixed-step enforcement:

- “The model is instructed to produce its final response after **20 iterations** …” (`_literature/markdown/giant/giant.md:126`)
- “We use a **system prompt to enforce** that the model provide its final response after a specific number of iterations, **marking a trial incorrect** if the model exceeds this limit after **3 retries**.” (`_literature/markdown/giant/giant.md:200`)
- Algorithm 1's structure (`_literature/markdown/giant/giant.md:151-161`) is explicit:
  - Loop body: `for t ← 1 to T−1 do … (rt, at) ← LLM(C)` where `at = (x, y, w, h)` — **crop coordinates only**
  - After loop: `ŷ ← LLM(C)` — **answer extracted only after loop terminates**
  - This enforces "T−1 crops, then final answer" with **no early-answer option** in the loop.
- The paper notes that for TCGA/PANDA, accuracy “continues to increase up to **20 iterations**” and the best configuration used `T=20` (`_literature/markdown/giant/giant.md:214-215`).

---

## Current Implementation (What We Do Today)

### 1) Prompts explicitly allow early answers

`src/giant/prompts/templates.py` includes:
- “Continue exploring **or answer** if you have sufficient evidence.” (`src/giant/prompts/templates.py:85-95`)

This directly contradicts fixed-step enforcement and encourages early stopping.

### 2) Agent accepts `answer` on any step (including step 1)

`GIANTAgent._handle_step_action()` immediately finalizes if the model returns `FinalAnswerAction` at any step:
- `src/giant/agent/runner.py:361-368`

There is no “answer only on final step” gating.

---

## Evidence This Skews Our Runs (Measured on Saved Artifacts)

All of the following runs were configured with `max_steps=20`, but **no item reached 20 steps** in the saved trajectories:

| Run ID | Dataset | Mean Steps Used | Max Steps Used | Config Max |
|---|---|---:|---:|---:|
| `tcga_giant_openai_gpt-5.2` | TCGA | 3.92 | 15 | 20 |
| `gtex_giant_openai_gpt-5.2` | GTEx | 2.81 | 10 | 20 |
| `panda_giant_openai_gpt-5.2` | PANDA | 10.28 | 19 | 20 |
| `tcga_slidebench_giant_openai_gpt-5.2` | SlideBenchVQA | 4.66 | 16 | 20 |
| `tcga_expert_vqa_giant_openai_gpt-5.2` | ExpertVQA | 4.20 | 16 | 20 |

Sources:
- `results/tcga_giant_openai_gpt-5.2_results.json`
- `results/gtex_giant_openai_gpt-5.2_results.json`
- `results/panda_giant_openai_gpt-5.2_results.json`
- `results/tcga_slidebench_giant_openai_gpt-5.2_results.json`
- `results/tcga_expert_vqa_giant_openai_gpt-5.2_results.json`
- Per-item trajectories under `results/trajectories/`

Interpretation:
- We are *not* running the paper’s “T=20 iterations” setting, even when configured for `max_steps=20`.
- For difficult tasks like TCGA/PANDA, the paper claims additional steps help up to 20. Early stopping is therefore a plausible contributor to our underperformance vs paper on those tasks.

---

## Impact

### Primary
- **Benchmark results are not paper-comparable** when using `max_steps=20`: the agent is frequently running a “T≈3–10” regime, not “T=20”.
- **Underperformance risk**: the paper reports that TCGA/PANDA improve with additional steps up to 20 (`_literature/markdown/giant/giant.md:214-215`).

### Secondary
- We likely **underuse navigation budget** on tasks where exploration matters, while still paying the overhead of the initial thumbnail + prompts.

---

## Proposed Fix (Paper-Fidelity Mode)

Add an explicit “paper-fidelity” enforcement mode (opt-in by default to avoid behavior surprises), e.g.:

1. **AgentConfig flag**
   - Add `enforce_fixed_iterations: bool = False` (name TBD) to `src/giant/agent/runner.py:AgentConfig`.

2. **Prompt tightening (paper-fidelity only)**
   - Replace permissive text in `src/giant/prompts/templates.py:85-95` so that before the final step the model must keep navigating (crop/conch) and must not answer early.
   - Keep current permissive behavior as the default “practical” mode if desired.

3. **Runtime enforcement in agent loop**
   - In `src/giant/agent/runner.py:_handle_step_action`:
     - If `enforce_fixed_iterations=True` and `not self._context.is_final_step` and action is `FinalAnswerAction`, treat it as out-of-contract:
       - Append a corrective user message: “Do not answer yet; continue navigating. You must answer on the final step.”
       - Re-call the LLM, counting toward the “3 retries then incorrect” policy, consistent with `_literature/markdown/giant/giant.md:200`.

4. **Expose via CLI / eval config**
   - Add a CLI option (e.g., `--paper-fidelity/--no-paper-fidelity`) and persist it into run metadata for auditability.

---

## Test Plan

Unit tests (mocked provider; no live calls):

1. **Early answer rejected when enforced**
   - Configure `AgentConfig(max_steps=3, enforce_fixed_iterations=True)`.
   - Mock provider returns `answer` at step 1, then `crop`, then `answer` at final step.
   - Assert: agent makes additional call(s) and only accepts the final-step answer.

2. **Early answer allowed when not enforced**
   - Same mock, but `enforce_fixed_iterations=False`.
   - Assert: agent returns immediately on early answer.

3. **Retry exhaustion yields failure**
   - With enforcement enabled, mock provider returns `answer` repeatedly before final step.
   - Assert: run fails after configured retry budget, matching paper’s “3 retries then incorrect” rule (`_literature/markdown/giant/giant.md:200`).

---

## Acceptance Criteria

- With `enforce_fixed_iterations=True`, trajectories always contain exactly `max_steps` turns for successful runs (unless terminated by budget/error), and answers occur only at the final step.
- With `enforce_fixed_iterations=False`, current behavior remains unchanged.
- Benchmarks can be rerun in paper-fidelity mode to measure whether TCGA/PANDA move toward paper-reported numbers.
