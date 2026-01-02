# BUG-043: Invalid Region Retry Premature Exit

**Date**: 2026-01-02
**Severity**: HIGH (blocks $265 benchmark run)
**Status**: ✅ FIXED (2026-01-02)
**Discovered by**: Deep code audit before PANDA benchmark

## Summary

When the LLM fails during invalid crop coordinate correction, `_handle_invalid_region()` could exit early with `None` (the function's “success” sentinel) instead of continuing retries. Because `ContextManager.current_step` is derived from the number of recorded turns, returning `None` without recording a turn could stall the step counter and trap the agent in an unbounded loop of repeated step-1 LLM calls.

## Location

- Primary: `src/giant/agent/runner.py` (`GIANTAgent._handle_invalid_region()`)
- Step counter coupling: `src/giant/agent/context.py` (`current_step = len(turns) + 1`)

## The Bug

```python
# Inside _handle_invalid_region() which uses a while True loop

try:
    response = await self.llm_provider.generate_response(
        messages_with_error
    )
    self._accumulate_usage(response)
except (LLMError, LLMParseError) as e:
    logger.warning("Retry LLM call failed: %s", e)
    self._consecutive_errors += 1
    if self._consecutive_errors >= self.config.max_retries:
        return self._build_error_result(
            f"Max retries ({self.config.max_retries}) exceeded: {e}"
        )
    return None  # <-- BUG: Should be 'continue', not 'return None'
```

**The problem**: `return None` exits the `while True` retry loop immediately. Per the function's docstring, returning `None` means "success" (valid crop completed). But we haven't succeeded - the LLM call failed.

### Additional (similar) bug in the same function

At the bottom of `_handle_invalid_region()`, the code currently treats any unexpected action type as a no-op and returns `None`:

```python
# _handle_invalid_region()
# ...
# Unexpected action type - treat as no-op
return None
```

In practice, the only “unexpected” `StepResponse.action` type here is `ConchAction` (since actions are a discriminated union of `crop` / `answer` / `conch`). Returning `None` here also signals “success” without recording a turn, which can stall the step counter and repeat the same step indefinitely.

## Impact

### What happens:

1. Agent requests invalid crop coordinates (e.g., out of bounds)
2. `_handle_invalid_region()` is called to correct them
3. First iteration: Retry LLM call to get corrected coordinates
4. LLM call raises `LLMError` or `LLMParseError`
5. Exception handler increments `_consecutive_errors` (now 1)
6. If not at max_retries yet, `return None` (exits loop)
7. Caller receives `None` = "success"
8. But no valid crop was returned!

### Caller behavior (why `None` is “success”)

```python
# _handle_crop_action()
result = await self._handle_crop(step_response, action, messages)
if result is not None:
    return _StepDecision(run_result=result)
return _StepDecision()  # None => treat as success
```

### Consequences:

1. **Potential infinite loop / hang**: no turn is recorded, so `current_step` never advances
2. **Token waste**: Repeated failed LLM calls accumulate cost
3. **Benchmark hangs**: 1-5% of files may trigger this scenario
4. **Budget overrun**: Runaway costs from loops

### Why this can become unbounded (step counter stall)

`ContextManager.current_step` is computed from the number of recorded turns:

```python
# src/giant/agent/context.py
return len(self.trajectory.turns) + 1
```

If `_handle_invalid_region()` returns `None` without calling `self._context.add_turn(...)`, the agent re-enters the navigation loop at the same step with the same message history, repeatedly paying for a new LLM call but making no progress.

## Reproduction

1. Run benchmark on a file where model returns out-of-bounds crop
2. Have the retry LLM call fail with RateLimitError (wrapped as LLMError)
3. Observe: Function returns None, loop may repeat indefinitely

## Fix

Implemented in `src/giant/agent/runner.py` by converting invalid-region correction to a
bounded retry loop that never returns “success” without recording a turn, and by
treating `ConchAction`/unexpected actions as retryable invalid outputs during correction.

## Correctness Notes (retry counting)

Lines 671 and 703 both increment `_consecutive_errors`:
- Line 671: At start of each loop iteration
- Line 703: Inside exception handler

This causes double-counting on LLM failures and interacts poorly with `max_retries`. A robust fix should:

- Use a local `attempt` counter (`for attempt in range(max_retries): ...`) instead of mutating `_consecutive_errors` twice.
- Treat `ConchAction` during invalid-region correction as invalid and retry with explicit feedback.

## Testing

Add test case:

```python
async def test_handle_invalid_region_llm_error_continues_retry(agent):
    """LLM error during invalid region correction should continue retry loop."""
    # Mock LLM to fail twice then succeed
    agent.llm_provider.generate_response.side_effect = [
        LLMError("Rate limit", provider="openai", model="gpt-5.2"),
        LLMError("Rate limit", provider="openai", model="gpt-5.2"),
        mock_valid_crop_response(),
    ]

    result = await agent._handle_invalid_region(
        invalid_action, messages, "Out of bounds"
    )

    assert result is None  # Success after retries
    assert agent._consecutive_errors == 0  # Reset on success
    assert agent.llm_provider.generate_response.call_count == 3
```

Also add a regression test that a `ConchAction` returned during invalid-region correction does **not** return `None` (success), but instead retries until `max_retries` is exhausted.

## Risk Assessment

| Scenario | Probability | Impact |
|----------|-------------|--------|
| PANDA 197 items | 1-5% trigger | 2-10 items may hang or fail unexpectedly |
| Token waste per item | ~$5-10 if loop runs | Budget overrun |
| Full benchmark | Could affect ~$10-50 | Noticeable but not catastrophic |

## Recommendation

**Fix this bug before the $265 PANDA benchmark run.**

The change is low-risk and prevents potential infinite loops that could waste significant budget.

This also aligns our retry/termination guardrails with the paper’s described “3 retries then incorrect” behavior when enforcing iteration limits (`_literature/markdown/giant/giant.md:200`).

## Related

- BUG-038-B7: Retry counter logic (previous fix for similar issue)
- BUG-038-B9: Recursive retry (refactored to iterative to avoid this class of bug)
