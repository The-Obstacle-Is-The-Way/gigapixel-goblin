# BUG-038-B9: Recursive Retry Handling

**Status**: FIXED (refactor implemented)
**Severity**: MEDIUM
**Component**: `src/giant/agent/runner.py`
**Fixed In**: `72df1b3` (fix: BUG-038-B9 refactor recursive retry to iterative loop)
**Pre-Refactor Commit**: `18ca397` (recursive retry)
**Lines (pre-refactor recursion block)**: 438-456
**Lines (fixed; iterative loop)**: 385-504
**Discovered**: 2025-12-29
**Audit**: Comprehensive E2E Bug Audit (8 parallel swarm agents)
**Parent Ticket**: BUG-038

---

## Summary

The `_handle_invalid_region()` method used recursion via `await self._handle_crop()` when the model returned a new crop action. While bounded by `max_retries` (default: 3), recursion is generally harder to reason about than iterative approaches.

---

## Original Code (pre-fix)

**File (pre-fix)**: `src/giant/agent/runner.py:438-456` (commit `18ca397`)

```python
# Process retry response
new_action = response.step_response.action

if isinstance(new_action, FinalAnswerAction):
    # Success: answer ends the run, reset error counter
    self._consecutive_errors = 0
    return self._handle_answer(response.step_response)

if isinstance(new_action, BoundingBoxAction):
    # Recursively try the new crop (will increment errors if still invalid)
    result = await self._handle_crop(
        response.step_response,
        new_action,
        messages,  # Use original messages
    )
    if result is None:
        # Success: crop recovered and recorded, reset error counter
        self._consecutive_errors = 0
    return result

return None
```

---

## Problem Analysis

### Pre-Refactor Behavior

1. `_handle_crop()` receives an invalid region
2. Calls `_handle_invalid_region()` to ask model for correction
3. Model returns new crop action
4. `_handle_invalid_region()` recursively calls `_handle_crop()` with new action
5. If still invalid, recursion continues

### Why This Worked (Pre-Refactor)

- **Bounded**: recursion depth is bounded by `max_retries` via `_consecutive_errors`
- **Functional**: Behavior is correct

### Why It's Not Ideal

1. **Stack depth**: Each retry adds a stack frame
2. **Reasoning complexity**: Harder to trace execution flow
3. **Error recovery**: Stack unwinding on deep failure is complex
4. **Testing**: Harder to mock intermediate states

---

## Impact Assessment

### Direct Impact

- **None currently**: Code works correctly
- **Future maintenance**: Harder to modify retry logic

### Risk Level

- **LOW**: No functional bugs, just code quality
- **Improvement**: Convert to iterative approach (now implemented)

---

## Fix Implementation

Implemented in `72df1b3` by refactoring `_handle_invalid_region()` to an iterative loop that:

- Builds error feedback, calls the LLM for corrected coordinates, and validates/crops within the loop.
- Uses `continue` on repeated invalid coordinates / crop failures, and exits on success or max retries.
- Preserves the existing behavior of *not* accumulating error-feedback messages into the persistent context history.

---

## Current Fixed Code

**File (fixed)**: `src/giant/agent/runner.py:385-504` (commit `72df1b3`)

```python
current_action = action
current_error = error_detail

while True:
    self._consecutive_errors += 1

    if self._consecutive_errors >= self.config.max_retries:
        return self._build_error_result(
            f"Max retries ({self.config.max_retries}) on invalid coordinates"
        )

    feedback = ERROR_FEEDBACK_TEMPLATE.format(
        x=current_action.x,
        y=current_action.y,
        width=current_action.width,
        height=current_action.height,
        max_width=self._slide_bounds.width,
        max_height=self._slide_bounds.height,
        issues=current_error,
    )

    error_message = Message(
        role="user",
        content=[MessageContent(type="text", text=feedback)],
    )
    messages_with_error = [*messages, error_message]

    response = await self.llm_provider.generate_response(messages_with_error)
    self._accumulate_usage(response)

    new_action = response.step_response.action
    if isinstance(new_action, FinalAnswerAction):
        self._consecutive_errors = 0
        return self._handle_answer(response.step_response)

    if isinstance(new_action, BoundingBoxAction):
        # Validate + crop; continue loop on failures.
        ...
        self._consecutive_errors = 0
        return None

    return None
```

---

## Test Plan

No new tests are required for correctness today (the current behavior is already covered by existing runner tests).

Verified these existing tests still pass:

- `tests/unit/agent/test_runner.py::TestGIANTAgentErrorRecovery::test_invalid_coordinates_then_valid`
- `tests/unit/agent/test_runner.py::TestGIANTAgentErrorRecovery::test_invalid_coordinates_recovery_resets_error_counter`
- `tests/unit/agent/test_runner.py::TestGIANTAgentErrorRecovery::test_max_retries_exceeded`

Run:

```bash
uv run pytest tests/unit/agent/test_runner.py -v
```

---

## Files to Modify

| File | Lines | Change |
|------|-------|--------|
| `src/giant/agent/runner.py` | 385-502 | Convert recursive retry to iterative loop |

---

## Dependencies

- **Blocked by**: None
- **Blocks**: None
- **Related**: B7 (retry counter logic)

---

## Sign-Off Checklist

- [x] Decision made: refactor to iterative or keep recursive
- [x] If refactoring: tests written for retry behavior (existing tests cover behavior)
- [x] If refactoring: iterative implementation completed
- [x] All test cases pass
- [x] Full test suite passes (`uv run pytest tests/unit`) — 826 passed
- [x] Type check passes (`uv run mypy src/giant`)
- [x] Lint passes (`uv run ruff check .`)
