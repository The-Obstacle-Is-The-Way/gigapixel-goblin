# Spec-09: GIANT Agent Core Loop

## Overview
This specification implements the main `GIANTAgent` class. This is the high-level controller that orchestrates the entire navigation process defined in Algorithm 1. It integrates the WSI data layer, the LLM provider, and the context manager to autonomously explore a slide and answer a question.

## Dependencies
- [Spec-05: Image Cropping & Resampling Pipeline](./spec-05-cropping.md)
- [Spec-06: LLM Provider Abstraction](./spec-06-llm-provider.md)
- [Spec-07: Navigation Prompt Engineering](./spec-07-navigation-prompt.md)
- [Spec-08: Conversation Context Manager](./spec-08-context-manager.md)

## Acceptance Criteria
- [x] `GIANTAgent` class is implemented.
- [x] `run()` method executes the navigation loop up to `max_steps`.
- [x] Correctly handles the initial "Thumbnail" step.
- [x] Correctly executes "Crop" actions using the `CropEngine`.
- [x] Correctly handles "Answer" actions (early stopping).
- [x] Returns a `RunResult` object containing the final answer and the full `Trajectory`.
- [x] Error handling: If LLM produces invalid coordinates or fails repeatedly, the agent should degrade gracefully (e.g., stop and return partial info).

## Technical Design

### Data Models

```python
from pydantic import BaseModel
from giant.agent.trajectory import Trajectory

class RunResult(BaseModel):
    answer: str
    trajectory: Trajectory
    total_tokens: int
    total_cost: float
    success: bool
    error_message: str | None = None
```

### Core Logic (`GIANTAgent.run`)

1.  **Initialize:**
    - Open WSI with `WSIReader`.
    - Create `ContextManager`.
    - Generate a 1024px Thumbnail + Axis Guides (`spec-03`, paper baseline uses 1024×1024 thumbnails).
    - Add Thumbnail to Context (Turn 0).

2.  **Navigation Loop** (t = 1 to T−1):
    - **Prompt:** `messages = context_manager.get_messages()`.
    - **LLM Call:** `response = await llm_provider.generate_response(messages)`.
    - **Enforce crop:** At steps 1..T−1, the model MUST return `BoundingBoxAction`.
        - If model returns `FinalAnswer` early, log warning but accept (early termination).
    - **Validate:** Validate bbox using `GeometryValidator` (strict by default; clamp only as an explicit, test-covered recovery path).
    - **Act:** `cropped_img = crop_engine.crop(region, target_size=llm_provider.get_target_size())`.
        - **Paper fidelity:** Use 1000px crops for OpenAI models and 500px crops for Anthropic models (paper note on Claude image pricing).
    - **Record:** Append `(reasoning, action, cropped_img)` to Context/Trajectory.

3.  **Final Answer** (t = T):
    - Make one final LLM call with full context, requiring `FinalAnswerAction`.
    - **Enforcement:** If model attempts another crop at step T:
        - Send corrective message: "You have reached the maximum navigation steps. You MUST provide your final answer now using the `answer` action."
        - Retry up to **3 times**.
        - After 3 failures: terminate with `success=False, error_message="Exceeded step limit after 3 retries"`.
        - **For benchmarking:** This counts as incorrect (paper evaluation policy).
    - Return `RunResult`.

### Budget / Cost Guardrails (Production-Readiness)
To prevent runaway costs during long runs (benchmarks or retries), `GIANTAgent.run()` should accept an optional `budget_usd: float | None`.
- If `total_cost >= budget_usd` at any point, force finalization:
  - Add a User message using `FORCE_ANSWER_TEMPLATE` noting the budget was reached.
  - Make a final LLM call requiring `FinalAnswerAction`.
  - Return `success=False` with `error_message="Budget exceeded"` (benchmark counts as incorrect).

### Error Handling
- **Invalid Coordinate Loop:** If the LLM tries to crop outside the image, catch the `ValidationError`, feed it back to the LLM as a User message using the template below, and retry.
- **Max Retries:** If it fails 3 times in a row on the same step, terminate with partial result.
- **Retry Counter:** Track `consecutive_errors: int` and reset to 0 on successful action.

#### Error Feedback Template
```python
ERROR_FEEDBACK_TEMPLATE = """
Error: Your crop coordinates were invalid.
Requested region: x={x}, y={y}, width={width}, height={height}
Image bounds: width={max_width}, height={max_height}

Issues:
{issues}

Please re-examine the axis guides on the thumbnail and provide valid Level-0 coordinates.
Your coordinates must satisfy:
- 0 <= x < {max_width}
- 0 <= y < {max_height}
- x + width <= {max_width}
- y + height <= {max_height}
"""
```

#### Force-Answer Template (Max Steps Reached)
```python
FORCE_ANSWER_TEMPLATE = """
You have reached the maximum number of navigation steps ({max_steps}).
Based on all the regions you have examined, you MUST now provide your final answer.

Review your observations:
{observation_summary}

Question: {question}

Provide your best answer using the `answer` action.
"""
```

## Test Plan

### Unit Tests (Mocked LLM)
1.  **Happy Path:** Mock LLM to return `Crop` -> `Crop` -> `Answer`. Verify 3 steps in trajectory.
2.  **Early Stop:** Mock LLM to return `Answer` immediately.
3.  **Loop Limit:** Mock LLM to always `Crop`. Verify it stops at `max_steps` and force-answer is invoked.
4.  **Error Recovery:** Mock LLM to return invalid coords, then valid coords. Verify retry works.
5.  **Max Retries:** Mock LLM to return invalid coords 3 times. Verify graceful termination.
6.  **Force Answer Content:** Verify force-answer prompt includes observation summary.

### Integration Tests
- **"Dry Run":** Run with a real `OpenAIProvider` (if configured) but a dummy image/mocked WSI to test the full message passing pipeline (without spending heavy credits on vision).

## File Structure
```text
src/giant/agent/
├── runner.py       # GIANTAgent implementation
tests/unit/agent/
└── test_runner.py
```
