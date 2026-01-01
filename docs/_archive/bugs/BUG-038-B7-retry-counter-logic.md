# BUG-038-B7: Retry Counter Resets After Recovery

**Status**: FIXED (2025-12-29)
**Severity**: MEDIUM
**Component**: `src/giant/agent/runner.py`
**Fixed In**: `f9465368` (fix: BUG-038-B7 reset error counter after successful recovery)
**Buggy Commit**: `f81b0cb2` (feat(agent): implement Spec-09 GIANT Agent core loop)
**Current Lines (fixed)**: `runner.py:439-456`
**Buggy Lines (pre-fix)**: `runner.py:401-413`
**Discovered**: 2025-12-29
**Audit**: Comprehensive E2E Bug Audit (8 parallel swarm agents)
**Parent Ticket**: BUG-038

---

## Summary

GIANTAgent uses `_consecutive_errors` to terminate after `max_retries` consecutive failures. Invalid crop coordinates are treated as an error and can be recovered by prompting the model for corrected coordinates.

Pre-fix, the invalid-region recovery path could succeed (valid crop executed or final answer returned) **without resetting `_consecutive_errors` to 0**, allowing a recovered failure to “leak” into later steps and prematurely exhaust retries under compound failure conditions.

Fixed in `f9465368` by resetting `_consecutive_errors = 0` after a successful recovery crop or answer, and adding a regression test.

---

## Original Buggy Code (pre-fix)

**File (pre-fix)**: `src/giant/agent/runner.py:401-413` (commit `f81b0cb2`)

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
```

---

## Current Fixed Code

**File (fixed)**: `src/giant/agent/runner.py:439-456` (commit `f9465368`)

```python
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
```

---

## Regression Test

**File**: `tests/unit/agent/test_runner.py`

- `TestGIANTAgentErrorRecovery::test_invalid_coordinates_recovery_resets_error_counter`

This test simulates:

1) invalid crop → recovery prompt
2) recovery crop succeeds
3) next step has two transient `LLMError`s and then an answer

Expected: run succeeds with `max_retries=3` (the recovered invalid crop must not “consume” a retry in the next step).

---

## Verification Steps

```bash
uv run pytest tests/unit/agent/test_runner.py::TestGIANTAgentErrorRecovery::test_invalid_coordinates_recovery_resets_error_counter -v
uv run pytest tests/unit/agent/test_runner.py -v
uv run pytest tests/unit -x
uv run mypy src/giant
uv run ruff check .
```
