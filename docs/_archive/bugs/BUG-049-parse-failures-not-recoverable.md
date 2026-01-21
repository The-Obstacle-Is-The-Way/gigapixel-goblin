# BUG-049: Parse Failures Not Recoverable (Raw Responses Not Persisted)

**Date**: 2026-01-21
**Severity**: P1 (High) — paid model outputs + usage can be lost on parse failure
**Status**: ✅ FIXED (2026-01-21)
**Discovered by**: Audit of GTEx 6 parse failures

## Summary

When LLM parsing fails (e.g., JSON "Extra data" errors), the raw LLM response is
**not persisted** in evaluation artifacts. This means:

1. Failed items cannot be recovered or re-scored without making new LLM calls
2. The raw text that caused the failure is lost forever
3. Debugging and root cause analysis is harder
4. Users cannot manually extract answers from malformed responses
5. Token usage/cost can be undercounted for those failed attempts

## Evidence

### GTEx Benchmark: 6 Unrecoverable Failures

From `results/_archive/pre-2026-01-01-fixes-20260101_192426/gtex_giant_openai_gpt-5.2_results.json`:

```json
{
  "item_id": "GTEX-14AS3-2026",
  "prediction": "",              // <-- Empty! Raw response lost
  "predicted_label": null,
  "truth_label": 4,
  "correct": false,
  "cost_usd": 0.0,               // <-- Usage not tracked either
  "total_tokens": 0,
  "trajectory_file": "results/trajectories/GTEX-14AS3-2026_run0.json",
  "error": "Max retries (3) exceeded: Failed to parse JSON: Extra data: line 1 column 376 (char 375)"
}
```

All 6 failed items have:
- `prediction: ""` (empty string, not the raw response)
- `cost_usd: 0.0` (API cost not tracked)
- `total_tokens: 0` (token usage lost)
- A trajectory file exists, but contains **0 turns** and no raw response text (nothing to recover)

### Root Cause

The providers raise `LLMParseError(raw_output=...)`, but callers discard it.

```python
# src/giant/llm/openai_client.py
raise LLMParseError(..., raw_output=output_text, provider="openai", model=self.model)
```

The `LLMParseError` does contain `raw_output`, but the agent/baseline callers do not
persist it anywhere:

- `src/giant/agent/runner.py`: `_call_llm_step()` catches `LLMParseError` and only logs
  `str(e)` (no raw output) before retrying or terminating.
- `src/giant/core/baselines.py`: `run_baseline_answer()` catches `LLMParseError` and
  retries, but does not persist raw output on failure.

Additionally, both providers compute `TokenUsage` **after** parsing. When parsing fails,
usage is never returned to the caller, so cost/tokens are undercounted:

- `src/giant/llm/openai_client.py`: usage/cost calculated after `StepResponse.model_validate(...)`
- `src/giant/llm/anthropic_client.py`: usage/cost calculated after tool input parsing

## Impact

### Current State (GTEx)
- **70.3%** balanced accuracy on 185/191 scored items
- **67.6%** paper-faithful (counting 6 failures as incorrect)
- Gap of **2.7 percentage points** due to unrecoverable failures

### Why This Matters

1. **Lost data**: The LLM DID generate responses for these 6 items. We paid for
   them but cannot use them.

2. **Irreproducibility**: Re-running with the SAME model may produce different
   responses (non-deterministic even at temp=0 with streaming).

3. **Debugging blind spot**: We cannot analyze WHY parsing failed without the
   raw text.

4. **Manual recovery impossible**: A human could potentially extract the answer
   from malformed JSON, but the text is gone.

## Proposed Fix

### Option A: Persist raw output + usage on parse failures (Recommended)

1. Attach token usage to `LLMParseError` (when available) so callers can still
   accumulate cost/tokens.
2. When a run terminates due to parse failures, persist the last `raw_output`
   into the results artifact (e.g., store it in `BenchmarkResult.prediction` or
   a dedicated `raw_output` field).

```python
# In src/giant/llm/protocol.py
class LLMParseError(LLMError):
    def __init__(..., raw_output: str | None = None, usage: TokenUsage | None = None):
        self.raw_output = raw_output
        self.usage = usage

# In src/giant/agent/runner.py and src/giant/core/baselines.py
except LLMParseError as e:
    if e.usage is not None:
        accumulate(e.usage)  # cost/tokens still counted
    last_raw_output = e.raw_output
```

### Option B: Rerun failed items only (separate backlog item)

See **BUG-050** for a proposed `--recover-failures` workflow. This doc focuses on
preserving raw outputs so recovery is possible without re-running paid calls.

## Best Practices (Industry Standard)

Per [Langfuse LLM Evaluation Best Practices](https://langfuse.com/blog/2025-03-04-llm-evaluation-101-best-practices-and-challenges):

> "By following a trace from input to output, you can spot where the model
> stumbles. Feed learnings from production back into development. If you spot
> new failure modes in the wild, incorporate them into your offline test sets."

This requires **preserving the raw outputs** that caused failures.

Per [Databricks LLM Evaluation](https://www.databricks.com/blog/best-practices-and-methods-llm-evaluation):

> "To monitor evaluations in production, teams can use a pipeline to log live
> LLM requests including prompts, responses, and metadata."

## Acceptance Criteria

- [x] When parsing fails, raw output is preserved somewhere in evaluation artifacts
      (so failures are recoverable / manually scorable).
- [x] Token usage/cost is accumulated even when parsing fails.
- [x] Failed items contain the raw response text in the persisted results output.

## Resolution

Implemented:

- Providers compute `TokenUsage` before parsing and attach it to `LLMParseError`:
  - `src/giant/llm/openai_client.py`
  - `src/giant/llm/anthropic_client.py`
  - `src/giant/llm/protocol.py` (`LLMParseError.usage`)
- Callers accumulate parse-failure usage and preserve the last `raw_output` on failure:
  - `src/giant/agent/runner.py`
  - `src/giant/core/baselines.py`

## Related

- **BUG-038-B2**: The JSON "Extra data" parsing bug that caused these failures (FIXED)
- **BUG-050**: No "rerun failed items only" capability (NEW)

## Workaround (Current)

For the existing 6 GTEx failures, the ONLY option is to re-run the full
benchmark with the fixed code. The raw responses are permanently lost.

For paper-faithful reporting, count the 6 failures as incorrect:
- **70.3%** → **67.6% ± 3.1%** (still beats paper's 60.7%)
