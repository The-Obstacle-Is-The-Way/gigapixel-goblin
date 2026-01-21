# BUG-049: Parse Failures Not Recoverable (Raw Responses Not Persisted)

**Date**: 2026-01-21
**Severity**: P2 (Medium) — affects evaluation completeness and reproducibility
**Status**: OPEN
**Discovered by**: Audit of GTEx 6 parse failures

## Summary

When LLM parsing fails (e.g., JSON "Extra data" errors), the raw LLM response is
**not persisted** before the exception is raised. This means:

1. Failed items cannot be recovered or re-scored without making new LLM calls
2. The raw text that caused the failure is lost forever
3. Debugging and root cause analysis is harder
4. Users cannot manually extract answers from malformed responses

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
- No trajectory file created

### Root Cause

In `src/giant/llm/openai_client.py`, the exception is raised BEFORE the raw
response is captured:

```python
try:
    decoder = json.JSONDecoder()
    raw_data, end_idx = decoder.raw_decode(output_text, idx=leading_ws)
    # ...
except json.JSONDecodeError as e:
    raise LLMParseError(  # <-- Raises immediately, loses output_text in caller
        f"Failed to parse JSON: {e}",
        raw_output=output_text,  # raw_output is in the exception but not persisted
        provider="openai",
        model=self.model,
    )
```

The `LLMParseError` does contain `raw_output`, but the calling code in
`agent/runner.py` does not persist this to the results file.

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

### Option A: Persist raw response before parsing (Recommended)

Modify `ItemExecutor` to always save the raw LLM response to the trajectory,
even when parsing fails:

```python
# In src/giant/eval/executor.py or agent/runner.py

try:
    step_response = await provider.generate_response(...)
except LLMParseError as e:
    # Save the raw response for debugging/recovery
    trajectory.add_failed_step(
        raw_response=e.raw_output,
        error=str(e),
        usage=e.usage if hasattr(e, 'usage') else None,
    )
    raise
```

### Option B: Add retry-with-recovery mode

Add a `--recover-failures` flag to the benchmark CLI that:
1. Loads the existing results file
2. Identifies items with `error != null`
3. Re-runs ONLY those items (with the now-fixed parser)
4. Merges the new results back

### Option C: Store all raw responses in a separate log

Create a `raw_responses.jsonl` file that logs every LLM response immediately
after receiving it, before any parsing:

```python
# At the start of _call_with_retry, after getting response
with open("results/raw_responses.jsonl", "a") as f:
    f.write(json.dumps({
        "item_id": current_item_id,
        "timestamp": datetime.utcnow().isoformat(),
        "raw_response": output_text,
    }) + "\n")
```

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

- [ ] Raw LLM responses are persisted BEFORE parsing (so failures are recoverable)
- [ ] Failed items include the raw response text in results.json
- [ ] Token usage is tracked even for parse failures
- [ ] A `--recover-failures` CLI option exists to re-run only failed items
- [ ] Documentation updated to explain recovery process

## Related

- **BUG-038-B2**: The JSON "Extra data" parsing bug that caused these failures (FIXED)
- **BUG-050**: No "rerun failed items only" capability (NEW)

## Workaround (Current)

For the existing 6 GTEx failures, the ONLY option is to re-run the full
benchmark with the fixed code. The raw responses are permanently lost.

For paper-faithful reporting, count the 6 failures as incorrect:
- **70.3%** → **67.6% ± 3.1%** (still beats paper's 60.7%)
