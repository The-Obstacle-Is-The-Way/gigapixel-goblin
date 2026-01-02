# BUG-045: CONCH Disabled Retry Guard Never Trips (Consumes Steps Without Termination)

**Date**: 2026-01-02
**Severity**: LOW (P3) — can waste steps and degrade accuracy if triggered
**Status**: ✅ FIXED (2026-01-02)
**Discovered by**: Adversarial audit during benchmark hardening

## Summary

When `enable_conch=False`, the agent previously tried to treat a model-produced `conch` action as an error and terminate after `max_retries`. In practice, this guard never tripped because `_consecutive_errors` is reset to `0` on every successful LLM call **before** action handling, so each disabled-CONCH event started from zero and was incremented to one.

Net effect: repeated `conch` requests can consume navigation steps (turns) without ever hitting the “max retries” termination path.

## Locations

- `src/giant/agent/runner.py` (`GIANTAgent._handle_step_action`, `GIANTAgent._handle_conch_disabled`)

## The Bug

The agent resets `_consecutive_errors` after any successful LLM response:

```python
# src/giant/agent/runner.py
response = await self.llm_provider.generate_response(messages)
self._accumulate_usage(response)
...
self._consecutive_errors = 0
return response, None
```

Then, if that successful response is a `ConchAction` while `enable_conch=False`, it increments `_consecutive_errors` and *attempts* to terminate after `max_retries`:

```python
# src/giant/agent/runner.py
if not self.config.enable_conch:
    self._context.add_turn(...)
    self._consecutive_errors += 1
    if self._consecutive_errors >= self.config.max_retries:
        return _StepDecision(run_result=self._build_error_result(...))
    return _StepDecision()
```

Because `_call_llm_step()` resets the counter immediately before `_handle_conch_action()` is invoked, `_consecutive_errors` is effectively always `1` here, and the `>= max_retries` branch is unreachable under normal execution.

## Impact

- **Step budget waste**: the invalid action is recorded as a turn (`add_turn`), advancing `current_step` and reducing remaining crops.
- **No “3 strikes” termination** for this invalid action type: a model that keeps requesting CONCH can burn through steps until the final-step force-answer path, instead of failing fast after retries.
- **Potential accuracy hit**: fewer useful crop steps are available.

This is likely rare (the prompt only mentions CONCH when enabled), but it is a correctness issue in the retry/guardrail logic.

## Fix

Implemented Option A: disabled-CONCH now re-prompts with feedback without recording
a turn and terminates after `max_retries` failed attempts.

## Tests to Add

- A unit test where the LLM repeatedly returns `ConchAction` with `enable_conch=False` and `max_retries=3`, asserting the run terminates with an error after 3 attempts (and does not advance `current_step` via recorded turns in Option A).

## Acceptance Criteria

- Disabled-CONCH requests either (A) do not consume steps and terminate after `max_retries`, or (B) terminate after `max_retries` in a clearly defined way.
- No changes to enabled-CONCH behavior.
