# BUG-020: Official System Prompts Not Incorporated (Supplementary Material Missing)

## Severity: P3 (Paper faithfulness / reproducibility)

## Status: Open (Blocked on Supplementary Material)

## Description

The GIANT paper states that the system prompt text used for OpenAI and Anthropic models is included in the **Supplementary Material**, which is not present in this repo. Our prompt templates are therefore reverse-engineered placeholders, so we cannot claim a verbatim reproduction of the paper’s prompting strategy.

This bug is about **paper reproducibility**, not functional correctness of the agent loop.

---

## Paper Evidence (Verbatim)

The paper explicitly states the prompts are in the Supplementary Material:

From `_literature/markdown/giant/giant.md` (line 142):

> "The system prompt used for OpenAI and Anthropic models is included in the Supplementary Material."

The Figure 4 caption also points to the Supplementary Material:

From `_literature/markdown/giant/giant.md` (line 126):

> "See Supplementary Material for prompts."

---

## What We Can Reliably Extract From the Paper (High Confidence)

Even without the Supplementary Material, the paper defines invariants that the prompts must communicate.

### Agent loop contract (Algorithm 1)

From `_literature/markdown/giant/giant.md` (lines 151-161):

> `P0 = {q, nav instructions + "at most T-1 crops"};`
>
> `for t ← 1 to T−1 do`
>
> `(rt, at) ← LMM(C) ; // at = (x, y, w, h)`

This implies the prompt (at minimum) must:
- communicate a crop/step budget (“at most T-1 crops”)
- require the model to output an action bounding box `(x, y, w, h)` per step
- accumulate multimodal context across steps (image + prior reasoning/actions)

### Coordinate system + axis guides (Sec 4.1)

From `_literature/markdown/giant/giant.md` (line 134):

> "To orient the model, the thumbnail is overlaid with four evenly spaced axis guides along each dimension, labeled with absolute level-0 pixel coordinates. At each step, the agent outputs a bounding box aᵗ = (xᵗ, yᵗ, wᵗ, hᵗ) in level-0 coordinates, specifying the next region of interest."

This implies the prompt must explain Level-0 coordinate space and that the axis guides provide absolute pixel coordinates used to pick `(x, y, w, h)`.

### Step-limit enforcement (Fig 5 caption)

From `_literature/markdown/giant/giant.md` (line 200):

> "We use a system prompt to enforce that the model provide its final response after a specific number of iterations, marking a trial incorrect if the model exceeds this limit after 3 retries."

This implies the system prompt includes explicit “final answer by iteration T” enforcement and a retry policy for violations during evaluation.

---

## What We Cannot Reliably Reconstruct (Must Not Guess)

Without the Supplementary Material we cannot verify, and therefore should not assert as fact:
- the exact system prompt strings (verbatim wording)
- whether prompts differ between OpenAI and Anthropic (beyond the paper’s statement that both exist)
- any required output formatting beyond the `(rᵗ, aᵗ)` contract (e.g., explicit JSON text included in the prompt)
- any additional constraints not stated in the main paper text

---

## Current State in This Repo

Code reference: `src/giant/prompts/templates.py`

- The file itself explicitly notes the prompts are placeholders pending Supplementary Material.
- The templates implement many paper-required invariants (Level-0 coordinate system, crop/answer actions, and step-limit instructions).

Note: Output formatting is enforced structurally by the provider integrations (OpenAI uses strict JSON-schema structured output; Anthropic uses forced tool use). This improves parsing reliability, but may differ from how the paper authors enforced formatting in their experiments.

---

## Proposed Fix (SSOT / Reproducibility)

1. Obtain the Supplementary Material prompt text(s) referenced by the paper (OpenAI + Anthropic variants, if different).
2. Integrate the verbatim prompts into `src/giant/prompts/templates.py` (or a provider-specific prompt module).
3. Add regression tests that lock the *paper-required invariants* (coordinate system, bbox format, crop limit, final-answer enforcement), and document any intentional divergence (e.g., structured-output enforcement).
4. Keep a clear provenance note (source + date) to prevent future drift.

---

## References

- GIANT paper: `_literature/markdown/giant/giant.md`
  - Fig 4 caption (prompts in Supplementary): line 126
  - Axis guides + Level-0 bbox (Sec 4.1): line 134
  - System prompt in Supplementary: line 142
  - Algorithm 1 (GIANT): lines 151-161
  - Fig 5 caption (step-limit enforcement): line 200
- Current templates: `src/giant/prompts/templates.py`
