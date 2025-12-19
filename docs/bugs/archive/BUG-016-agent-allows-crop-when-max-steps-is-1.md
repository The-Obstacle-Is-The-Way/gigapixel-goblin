# BUG-016: Agent Executes Crop When `max_steps=1` (Contract Violation + Trajectory Inconsistency)

## Severity: P2 (High Priority) - Correctness / Contract

## Status: Open

## Description

When `AgentConfig(max_steps=1)`, the prompt explicitly marks step 1 as the **final** step and instructs the model to use `answer`.

However, if the model returns a `crop` action anyway, `GIANTAgent` will:

1. Execute the crop via `CropEngine.crop(...)` even though no crops are allowed.
2. Add a crop turn to the trajectory.
3. Then force an answer via `_force_final_answer()`.

This violates the Spec-07/Spec-09 “final step must answer” contract and creates a subtle provenance issue: the forced-answer call does not include the final-step crop image in the user message (because the ContextManager step guard prevents adding a next-step user message), but the trajectory can still end up recording the crop image as the “observation” image for the answer turn.

## Reproduction (Validated)

With mocked components:

- Set `AgentConfig(max_steps=1)`
- Make the LLM return `crop` on the first call and `answer` on the force-answer call
- Observe: `CropEngine.crop` is invoked and the trajectory contains 2 turns (crop + answer)

## Expected Behavior

If `current_step == max_steps` (no remaining steps):

- A `crop` action should be treated as out-of-contract.
- The agent should **not** execute the crop.
- The agent should immediately force an answer (or return an error if force-answer retries fail).

## Code Location

- `src/giant/agent/runner.py`
  - `_navigation_loop()` routes all `BoundingBoxAction` through `_handle_crop(...)` without checking if any crops are allowed for the current step.
  - `_force_final_answer()` uses `ContextManager.get_messages()`, which intentionally does not append a next-step user message once the step limit is reached.

## Impact

- Violates the step contract for edge configs (and wastes time/resources executing a crop that the model won’t actually get to observe in the forced-answer call).
- Can produce misleading trajectories (answer appears to be based on an unseen crop).

## Proposed Fix

In `_navigation_loop()`:

- Before calling `_handle_crop(...)`, add a guard:
  - If `self._context.current_step >= self.config.max_steps`: do not crop; go straight to `_force_final_answer()`.

Optionally:

- Validate config early: reject `max_steps < 2` for “navigation mode”, or treat `max_steps=1` as “thumbnail baseline” behavior.

## Testing Required

- New unit test: `max_steps=1` + model returns crop → crop engine is not called and agent forces answer.
