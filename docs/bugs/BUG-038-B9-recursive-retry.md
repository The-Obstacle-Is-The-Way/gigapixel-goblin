# BUG-038-B9: Recursive Retry Handling

**Status**: IMPROVEMENT (refactor; not a functional bug)
**Severity**: MEDIUM
**Component**: `src/giant/agent/runner.py`
**Lines**: 444-450
**Discovered**: 2025-12-29
**Audit**: Comprehensive E2E Bug Audit (8 parallel swarm agents)
**Parent Ticket**: BUG-038

---

## Summary

The `_handle_invalid_region()` method uses recursion via `await self._handle_crop()` when the model returns a new crop action. While bounded by `max_retries=3`, recursion is generally harder to reason about than iterative approaches.

---

## Current Code

**File**: `src/giant/agent/runner.py:438-451`

```python
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

### Current Behavior

1. `_handle_crop()` receives an invalid region
2. Calls `_handle_invalid_region()` to ask model for correction
3. Model returns new crop action
4. `_handle_invalid_region()` recursively calls `_handle_crop()` with new action
5. If still invalid, recursion continues

### Why This Works (Currently)

- **Bounded**: `_consecutive_errors` prevents infinite recursion (max 3 retries)
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
- **Improvement**: Convert to iterative approach

---

## Fix Implementation

This is an optional refactor only.

- The current recursion is bounded by `max_retries` (default: 3) and is therefore safe in practice.
- Refactoring `_handle_invalid_region()` into an iterative loop is reasonable if/when retry semantics grow more complex.
- If you refactor, avoid duplicating `_handle_crop()` logic; preserve current behavior exactly.

---

## Test Plan

No new tests are required for correctness today (the current behavior is already covered by existing runner tests).

If you refactor, ensure these existing tests still pass:

- `tests/unit/agent/test_runner.py::TestGIANTAgentErrorRecovery::test_invalid_coordinates_then_valid`
- `tests/unit/agent/test_runner.py::TestGIANTAgentErrorRecovery::test_max_retries_exceeded`

Run:

```bash
uv run pytest tests/unit/agent/test_runner.py -v
```

---

## Files to Modify

| File | Lines | Change |
|------|-------|--------|
| `src/giant/agent/runner.py` | 385-451 | Convert to iterative loop (optional) |

---

## Dependencies

- **Blocked by**: None
- **Blocks**: None
- **Related**: B7 (retry counter logic)

---

## Sign-Off Checklist

- [ ] Decision made: refactor to iterative or keep recursive
- [ ] If refactoring: tests written for retry behavior
- [ ] If refactoring: iterative implementation completed
- [ ] All test cases pass
- [ ] Full test suite passes (`uv run pytest tests/unit`)
- [ ] Type check passes (`uv run mypy src/giant`)
- [ ] Lint passes (`uv run ruff check .`)
