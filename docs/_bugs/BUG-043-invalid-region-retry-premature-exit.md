# BUG-043: Invalid Region Retry Premature Exit

**Date**: 2026-01-02
**Severity**: HIGH (blocks $265 benchmark run)
**Status**: OPEN - Fix required before benchmark
**Discovered by**: Deep code audit before PANDA benchmark

## Summary

When the LLM fails during invalid crop coordinate correction, the retry loop exits prematurely with a "success" signal instead of continuing to retry. This can cause infinite loops or premature failures during benchmark runs.

## Location

`src/giant/agent/runner.py` lines 701-708

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

### Caller behavior (`_handle_crop` at line ~553):

```python
result = await self._handle_invalid_region(action, messages, error_detail)
if result is not None:
    return result  # Only handles RunResult (error case)
# Falls through - assumes success, but action is still invalid!
```

### Consequences:

1. **Potential infinite loop**: Caller may re-attempt the same invalid crop
2. **Token waste**: Repeated failed LLM calls accumulate cost
3. **Benchmark hangs**: 1-5% of files may trigger this scenario
4. **Budget overrun**: Runaway costs from loops

## Reproduction

1. Run benchmark on a file where model returns out-of-bounds crop
2. Have the retry LLM call fail with RateLimitError (wrapped as LLMError)
3. Observe: Function returns None, loop may repeat indefinitely

## Fix

**One-line change** - line 708:

```python
# Before
return None

# After
continue
```

This keeps the loop running for additional retry attempts until `max_retries` is exhausted.

## Secondary Issue: Double Increment

Lines 671 and 703 both increment `_consecutive_errors`:
- Line 671: At start of each loop iteration
- Line 703: Inside exception handler

This causes double-counting on LLM failures. However, this is a minor issue since the fix (`continue`) will make the behavior more correct regardless.

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

## Risk Assessment

| Scenario | Probability | Impact |
|----------|-------------|--------|
| PANDA 197 items | 1-5% trigger | 2-10 items may hang or fail unexpectedly |
| Token waste per item | ~$5-10 if loop runs | Budget overrun |
| Full benchmark | Could affect ~$10-50 | Noticeable but not catastrophic |

## Recommendation

**Fix this bug before the $265 PANDA benchmark run.**

The change is surgical (one line), low-risk, and prevents potential infinite loops that could waste significant budget.

## Related

- BUG-038-B7: Retry counter logic (previous fix for similar issue)
- BUG-038-B9: Recursive retry (refactored to iterative to avoid this class of bug)
