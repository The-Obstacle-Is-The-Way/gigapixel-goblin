# Spec-07: Navigation Prompt Engineering

## Overview
This specification defines the prompt templates and construction logic used to guide the LMM through the GIANT navigation task. It translates the abstract goal ("diagnose this slide") into specific, enforceable instructions for the model, ensuring it understands the coordinate system, the iteration limit, and the required output format.

## Dependencies
- [Spec-06: LLM Provider Abstraction](./spec-06-llm-provider.md)

## Acceptance Criteria
- [ ] `PromptBuilder` class is implemented.
- [ ] System prompt clearly explains the "Pathologist" persona, the level-0 coordinate system, and the available tools.
- [ ] User prompt dynamically inserts the Question and Iteration Status ("Step X of T").
- [ ] Prompt includes specific "Visual Cues" instructions (referencing the axis guides).
- [ ] Few-shot examples (optional but recommended) are defined for coordinate selection.

## Technical Design

### Note on Official Prompts
The paper states: "The system prompt used for OpenAI and Anthropic models is included in the Supplementary Material."

When the official prompts become available, replace the templates below. The current templates are reverse-engineered from Algorithm 1:
- Include "at most T-1 crops" phrasing per Algorithm 1
- Reference P0 = {q, nav instructions + "at most T-1 crops"}

### System Prompt Template

```text
You are GIANT (Gigapixel Image Agent for Navigating Tissue), an expert computational pathologist assistant.

YOUR GOAL:
Answer the user's question about a Whole Slide Image (WSI) by iteratively examining regions of interest.

THE IMAGE:
- You are viewing a gigapixel pathology slide.
- You cannot see the whole slide in full detail at once.
- You are currently provided with a view (either the full slide thumbnail or a zoomed-in crop).
- The thumbnail view has AXIS GUIDES overlaid. These red lines are labeled with ABSOLUTE LEVEL-0 PIXEL COORDINATES (e.g., 10000, 20000).
- ALL coordinates you output must be in this LEVEL-0 system.

YOUR TOOLS:
1. `crop(x, y, width, height)`: Zoom into a specific region.
   - `x`, `y`: Top-left corner in Level-0 coordinates.
   - `width`, `height`: Dimensions in Level-0 pixels.
   - Use the axis guides on the thumbnail to estimate these numbers.
2. `answer(text)`: Provide the final answer to the user's question.

PROCESS:
1. Analyze the current image. Look for tissue structures relevant to the question.
2. Provide `reasoning`: Explain what you see and why you need to zoom in or answer.
3. Choose an `action`:
   - If you need more detail, choose `crop`.
   - If you have sufficient evidence, choose `answer`.

CONSTRAINTS:
- You have a limited number of steps. Make every crop count.
- If the current view is blurry, it means you are looking at a thumbnail. You MUST zoom in to see cellular details.
```

### User Prompt Construction
The user prompt updates at every step to maintain state awareness.

**Initial Prompt (Paper-Faithful):**
```text
Question: {question}
Status: Step 1 of {max_steps}. You have {max_steps - 1} crops remaining.
Instruction: For Steps 1..{max_steps - 1} you MUST use `crop`. On Step {max_steps} you MUST use `answer`.
Image: [Thumbnail with Axis Guides]
```

**Subsequent Prompts:**
```text
Status: Step {current_step} of {max_steps}.
Last Action: You cropped region {last_region}.
Current View: [High-res Crop]
Image Context: [Thumbnail with Axis Guides (optional/repeated for reference)]
Question: {question}
```

### PromptBuilder Class

```python
class PromptBuilder:
    def build_system_message(self) -> Message: ...
    def build_user_message(self, question: str, step: int, max_steps: int, context_images: List[str]) -> Message: ...
```

## Test Plan

### Unit Tests
1.  **Template Rendering:** Verify variables (`question`, `max_steps`) are correctly substituted.
2.  **Instruction Check:** Assert that key phrases ("Level-0", "axis guides") are present in the output.

## File Structure
```text
src/giant/prompts/
├── __init__.py
├── templates.py    # Raw string templates
└── builder.py      # Logic to construct messages
tests/unit/prompts/
└── test_builder.py
```
