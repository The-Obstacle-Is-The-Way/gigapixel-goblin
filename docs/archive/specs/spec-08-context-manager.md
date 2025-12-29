# Spec-08: Conversation Context Manager

## Overview
This specification defines the `ContextManager` which maintains the state of the agent's navigation session. It tracks the sequence of observations (images), thoughts (reasoning), and actions. It is responsible for formatting this history into the list of messages expected by the `LLMProvider` and managing context window usage (e.g., by pruning old images if configured).

## Dependencies
- [Spec-06: LLM Provider Abstraction](./spec-06-llm-provider.md)

## Acceptance Criteria
- [ ] `ContextManager` class is implemented.
- [ ] `add_turn` method accepts `(image, reasoning, action)`.
- [ ] `get_messages` returns the full formatted conversation history for the LLM.
- [ ] `Trajectory` model stores the full history in a serializable format (JSON).
- [ ] Configurable "Image History Limit" (default: keep all). If exceeded, older images in the history are replaced with placeholder text to save tokens.

## Technical Design

### Data Models

```python
from pydantic import BaseModel
from typing import List, Optional
from giant.llm.protocol import StepResponse, Message
from giant.geometry.primitives import Region

class Turn(BaseModel):
    step_index: int
    image_base64: str  # The crop seen at this step
    response: StepResponse
    region: Optional[Region] = None # The region that was cropped to get here

class Trajectory(BaseModel):
    wsi_path: str
    question: str
    turns: List[Turn] = []
    final_answer: Optional[str] = None
```

### Context Management Logic
The `get_messages` method constructs the prompt sent to the LLM.
Structure:
1.  **System Message** (from PromptBuilder).
2.  **User Message (Turn 0)**: Initial Query + Thumbnail.
3.  **Assistant Message (Turn 0)**: Reasoning + Action (Crop 1).
4.  **User Message (Turn 1)**: "Here is the crop..." + Crop 1 Image.
5.  ...

**Token Optimization:**
If `max_history_images` is set (e.g., to 5) and we are at step 10:
- Keep the Thumbnail (always).
- Keep the last 5 crops (Step 5-9).
- For Steps 1-4, replace the `image_base64` in the User Message with text `[Image from Step X removed to save context]`. The reasoning/action text remains.

### Visualization Support
The `Trajectory` object can be dumped to JSON. This JSON is the input for the future `giant visualize` command.

## Test Plan

### Unit Tests
1.  **History Tracking:** Add 3 turns. Verify `get_messages` produces alternating User/Assistant messages.
2.  **Pruning:** Set `max_history_images=1`. Add 3 turns. Verify `get_messages` contains only the most recent image and the thumbnail (if treated special), and others are placeholders.
3.  **Serialization:** Verify `Trajectory` dumps to valid JSON and loads back.

## File Structure
```text
src/giant/agent/
├── __init__.py
├── context.py      # ContextManager implementation
└── trajectory.py   # Data models
tests/unit/agent/
└── test_context.py
```
