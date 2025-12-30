# BUG-038-B7: Asymmetric Retry Counter Logic

**Status**: CONFIRMED (not yet fixed)
**Severity**: MEDIUM
**Component**: `src/giant/agent/runner.py`
**Lines**: 261-452 (main loop reset + invalid-region recovery)
**Discovered**: 2025-12-29
**Audit**: Comprehensive E2E Bug Audit (8 parallel swarm agents)
**Parent Ticket**: BUG-038

---

## Summary

`GIANTAgent` tracks `_consecutive_errors` to stop after `max_retries` consecutive failures (Spec-09: reset the counter on a successful action).

Today, the invalid-region recovery path can *leave `_consecutive_errors` non-zero even after a successful recovery crop*, which means subsequent transient LLM errors can exhaust `max_retries` earlier than intended.

---

## Current Buggy Code

### Code Path 1: Main Navigation Loop (resets on successful LLM call)

**File**: `src/giant/agent/runner.py:269-282`

```python
try:
    response = await self.llm_provider.generate_response(messages)
    self._accumulate_usage(response)
except (LLMError, LLMParseError) as e:
    logger.warning("LLM call failed: %s", e)
    self._consecutive_errors += 1
    if self._consecutive_errors >= self.config.max_retries:
        return self._build_error_result(
            f"Max retries ({self.config.max_retries}) exceeded: {e}"
        )
    continue

# Reset error counter on success
self._consecutive_errors = 0
```

### Code Path 2: Invalid Region Handler (does not reset after a successful recovery crop)

**File**: `src/giant/agent/runner.py:385-452`

```python
async def _handle_invalid_region(
    self,
    action: BoundingBoxAction,
    messages: list[Message],
    error_detail: str,
) -> RunResult | None:
    """Handle invalid crop coordinates with retry.

    Args:
        action: The invalid bounding box action.
        messages: Current message history.
        error_detail: Description of the validation failure.

    Returns:
        RunResult if max retries exceeded, None to continue.
    """
    self._consecutive_errors += 1

    if self._consecutive_errors >= self.config.max_retries:
        return self._build_error_result(
            f"Max retries ({self.config.max_retries}) on invalid coordinates"
        )

    # Build error feedback message
    feedback = ERROR_FEEDBACK_TEMPLATE.format(
        x=action.x,
        y=action.y,
        width=action.width,
        height=action.height,
        max_width=self._slide_bounds.width,
        max_height=self._slide_bounds.height,
        issues=error_detail,
    )

    # Add error feedback to messages and retry
    error_message = Message(
        role="user",
        content=[MessageContent(type="text", text=feedback)],
    )
    messages_with_error = [*messages, error_message]

    try:
        response = await self.llm_provider.generate_response(messages_with_error)
        self._accumulate_usage(response)
    except (LLMError, LLMParseError) as e:
        logger.warning("Retry LLM call failed: %s", e)
        self._consecutive_errors += 1
        if self._consecutive_errors >= self.config.max_retries:
            return self._build_error_result(
                f"Max retries ({self.config.max_retries}) exceeded: {e}"
            )
        return None

    # Process retry response
    new_action = response.step_response.action

    if isinstance(new_action, FinalAnswerAction):
        return self._handle_answer(response.step_response)

    if isinstance(new_action, BoundingBoxAction):
        # Recursively try the new crop (will increment errors if still invalid)
        return await self._handle_crop(
            response.step_response,
            new_action,
            messages,  # Use original messages
        )

    return None
```

---

## Problem Analysis

### Root Cause

Per Spec-09, `_consecutive_errors` should reset to 0 after a successful action.

In the main loop, `_consecutive_errors` is reset to 0 immediately after a successful LLM call. But in the invalid-region recovery path, a successful recovery crop can be executed via the recursive `_handle_crop(...)` call and still return without resetting `_consecutive_errors`.

That makes failures from a recovered invalid crop “stick” into subsequent steps.

### Expected Behavior

After a successful recovery (valid crop executed, or answer returned), reset `_consecutive_errors` to 0 so subsequent transient failures start a fresh consecutive-error streak.

---

## Impact Assessment

### Direct Impact

- **Premature termination**: A recovered invalid crop can still “consume” 1 retry for the next step, so fewer transient failures are needed to hit `max_retries`.
- **Harder debugging**: Termination can look like “3 consecutive LLM failures” even if one of the counted failures was an already-recovered invalid crop.

### Observed Frequency

- **Uncommon**: Requires an invalid crop (validation/crop error) followed by transient LLM failures in a later step.
- **Plausible in production**: Invalid coordinates are common failure modes; rate limits/transient provider errors are also common.

### Risk Level

- **MEDIUM**: Logic bug that can reduce robustness under compound failure conditions.

---

## Fix Implementation

### Option A: Reset Counter After Successful Recovery (Recommended)

When `_handle_invalid_region()` successfully recovers by executing a valid crop (or returning an answer), reset `_consecutive_errors` to 0 before returning.

```python
if isinstance(new_action, FinalAnswerAction):
    # Success: answer ends the run
    self._consecutive_errors = 0
    return self._handle_answer(response.step_response)

if isinstance(new_action, BoundingBoxAction):
    result = await self._handle_crop(
        response.step_response,
        new_action,
        messages,  # Use original messages
    )
    if result is None:
        # Success: crop recovered and recorded
        self._consecutive_errors = 0
    return result
```

### Option B: Split Counters (Alternative, Larger Refactor)

If you want to make the semantics explicit, keep separate counters (LLM failures vs validation/crop failures) and use them to drive termination logic. This is more invasive but can improve maintainability.

### Recommendation

Implement **Option A** first (minimal + directly aligns with Spec-09’s “reset on success”).

---

## Test Cases

**File**: `tests/unit/agent/test_runner.py`

Add this test method to the existing `TestGIANTAgentErrorRecovery` class.

```python
    @pytest.mark.asyncio
    async def test_invalid_coordinates_recovery_resets_error_counter(
        self,
        mock_wsi_reader: MagicMock,
        mock_crop_engine: MagicMock,
        mock_llm_provider: MagicMock,
    ) -> None:
        """Recovered invalid coords should reset error counter (BUG-038-B7).

        Scenario:
        1) Step 1 LLM call returns invalid crop -> triggers _handle_invalid_region
        2) Retry LLM call returns valid crop -> crop succeeds
        3) Next step has 2 transient LLM errors, then succeeds with an answer

        Expected: With max_retries=3, the run should still succeed. The recovered
        invalid crop should not “carry” one retry into the next step.
        """
        invalid_crop = make_crop_response(99000, 74000, 5000, 5000)
        valid_crop = make_crop_response(1000, 1000, 500, 500)
        answer = make_answer_response("Recovered", "After transient errors")

        mock_llm_provider.generate_response.side_effect = [
            invalid_crop,
            valid_crop,
            LLMError("API error", provider="mock"),
            LLMError("API error", provider="mock"),
            answer,
        ]

        with patch("giant.agent.runner.WSIReader", return_value=mock_wsi_reader):
            with patch(
                "giant.agent.runner.CropEngine",
                return_value=mock_crop_engine,
            ):
                agent = GIANTAgent(
                    wsi_path="/test/slide.svs",
                    question="Is this malignant?",
                    llm_provider=mock_llm_provider,
                    config=AgentConfig(max_steps=5, max_retries=3),
                )
                result = await agent.run()

        assert result.success is True
        assert result.answer == "Recovered"
        assert mock_llm_provider.generate_response.call_count == 5
```

---

## Files to Modify

| File | Lines | Change |
|------|-------|--------|
| `src/giant/agent/runner.py` | 441-450 | Reset `_consecutive_errors` after successful recovery crop |

---

## Verification Steps

### 1. Write Failing Test First (TDD)

```bash
# Run test to confirm the recovered invalid crop still “consumes” one retry today
uv run pytest tests/unit/agent/test_runner.py::TestGIANTAgentErrorRecovery::test_invalid_coordinates_recovery_resets_error_counter -v
# Expected: FAIL (terminates after 4 calls; never reaches the final answer)
```

### 2. Apply Fix

In `_handle_invalid_region`, reset `_consecutive_errors` to 0 when the recovery crop succeeds (i.e., the recursive `_handle_crop(...)` returns `None`).

### 3. Verify Fix

```bash
# Run all runner tests
uv run pytest tests/unit/agent/test_runner.py -v

# Run full test suite
uv run pytest tests/unit -x

# Type check
uv run mypy src/giant

# Lint
uv run ruff check .
```

---

## Dependencies

- **Blocked by**: None
- **Blocks**: None
- **Related**: B9 (recursive retry handling)

---

## Complexity Warning

This fix touches retry semantics which affect agent reliability. **Consider:**

1. **Integration testing**: Run against real WSI files after fix
2. **Edge case review**: Ensure fix doesn't allow infinite retries
3. **Logging**: Add debug logs to track retry counter values

---

## Sign-Off Checklist

- [ ] Failing tests written for retry counter behavior
- [ ] Fix applied (reset counter after successful recovery)
- [ ] All test cases pass
- [ ] Integration test passes (optional but recommended)
- [ ] Full test suite passes (`uv run pytest tests/unit`)
- [ ] Type check passes (`uv run mypy src/giant`)
- [ ] Lint passes (`uv run ruff check .`)
- [ ] PR created and merged
