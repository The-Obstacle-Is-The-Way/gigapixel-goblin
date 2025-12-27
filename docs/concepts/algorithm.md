# Navigation Algorithm

This page explains GIANT's core navigation algorithm, based on Algorithm 1 from the paper.

## Overview

GIANT navigates gigapixel images through an iterative process:

1. Show the LLM a low-resolution thumbnail with coordinate guides
2. LLM reasons about what to examine and outputs a crop action
3. Extract the requested region at high resolution
4. Repeat until the LLM has enough information to answer

## Algorithm 1: GIANT Navigation

```
Input: WSI W, question q, step limit T
Output: answer ŷ

1.  I₀ ← Thumbnail(W)                    # Generate thumbnail
2.  I₀ ← AddAxisGuides(I₀)               # Add coordinate markers
3.  C ← [(system_prompt, q, I₀)]         # Initialize context
4.
5.  for t = 1 to T-1 do                  # At most T-1 crops (paper)
6.      (rₜ, aₜ) ← LLM(C)                 # Get reasoning + action
7.
8.      if aₜ.type == "answer" then
9.          return aₜ.text               # Early termination
10.
11.     if aₜ.type == "crop" then
12.         Iₜ ← CropRegion(W, aₜ, S)    # Extract region
13.         C ← C ∪ [(rₜ, aₜ, Iₜ)]        # Add to context
14.
15. end for
16.
17. ŷ ← ForceAnswer(C)                   # Final step: must answer (with retries)
18. return ŷ
```

## Step-by-Step Breakdown

### Step 1: Thumbnail Generation

```python
# Generate thumbnail fitting within max_size
thumbnail = reader.get_thumbnail((1024, 1024))
```

The thumbnail is a low-resolution overview of the entire slide. A 100,000 x 80,000 pixel slide becomes roughly 1024 x 820 pixels.

### Step 2: Axis Guides

```python
# Add Level-0 coordinate markers
navigable = overlay_service.create_navigable_thumbnail(thumbnail, metadata)
```

Red lines with pixel coordinate labels are overlaid:

```
     0        25000      50000      75000     100000
     │          │          │          │          │
  ───┼──────────┼──────────┼──────────┼──────────┼───
     │          │          │          │          │
     │    ┌─────────────────────┐     │          │
     │    │  Tissue visible     │     │          │
25K ─┼────│  in this region     │─────┼──────────┼───
     │    │                     │     │          │
     │    └─────────────────────┘     │          │
     │          │          │          │          │
50K ─┼──────────┼──────────┼──────────┼──────────┼───
```

The LLM uses these markers to specify exact coordinates.

### Step 3: Context Initialization

```python
context = ContextManager(
    wsi_path=wsi_path,
    question=question,
    max_steps=20,
)
```

The initial context includes:
- System prompt (navigation instructions)
- User question
- Thumbnail image with axis guides

### Steps 4-15: Navigation Loop

Each iteration:

1. **Build messages** from context (system, user turns, assistant turns)
2. **Call LLM** with multimodal input (text + images)
3. **Parse response** into reasoning + action
4. **Execute action**:
   - If `crop`: Extract region, add to context
   - If `answer`: Return immediately

### Step 17: Force Answer

If the LLM reaches the step limit without answering:

```python
force_prompt = """
You have reached the maximum number of navigation steps ({max_steps}).
Based on all the regions you have examined, you MUST now provide your final answer.
"""
```

The agent retries up to 3 times to get an answer action.

## Key Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `T` (max_steps) | 20 | Maximum navigation steps |
| `S` (target_size) | 1000 (OpenAI) / 500 (Anthropic) | Output crop long-side (provider-specific) |
| Thumbnail size | 1024 | Maximum thumbnail dimension |
| Max retries | 3 | Retries for invalid coordinates |
| Oversampling bias | 0.85 | Bias toward finer pyramid levels |

## Coordinate System

All coordinates use **Level-0** (full resolution) pixel space:

- `x`: Horizontal position from left edge
- `y`: Vertical position from top edge
- `width`, `height`: Size of region to extract

Example for a 100,000 x 80,000 slide:
```json
{
  "x": 45000,      // 45% from left
  "y": 20000,      // 25% from top
  "width": 10000,  // 10% of slide width
  "height": 10000  // 12.5% of slide height
}
```

## Level Selection

WSIs are stored as image pyramids with multiple resolution levels:

```
Level 0: 100,000 x 80,000 (full resolution)
Level 1:  50,000 x 40,000 (2x downsampled)
Level 2:  25,000 x 20,000 (4x downsampled)
Level 3:  12,500 x 10,000 (8x downsampled)
```

GIANT automatically selects the optimal level to:
1. Avoid upsampling (blurry results)
2. Minimize downsampling (preserve detail)
3. Output at target size (1000px)

```python
from giant.core.level_selector import PyramidLevelSelector
from giant.geometry import Region
from giant.wsi import WSIReader

with WSIReader("slide.svs") as reader:
    metadata = reader.get_metadata()

selector = PyramidLevelSelector()
selected = selector.select_level(
    region=Region(x=45000, y=20000, width=10000, height=10000),
    metadata=metadata,
    target_size=1000,
    bias=0.85,
)
```

## Error Handling

### Invalid Coordinates

If the LLM provides out-of-bounds coordinates:

1. Validate against slide dimensions
2. Send error feedback to LLM
3. Request corrected coordinates
4. Retry up to `max_retries` times

### Parse Errors

If the LLM output can't be parsed:

1. Log the raw output
2. Increment error counter
3. Retry with same context
4. Fail after `max_retries`

## Cost Optimization

Each LLM call has a cost. GIANT optimizes by:

1. **Early termination**: Answer as soon as evidence is sufficient
2. **Efficient context**: Don't repeat full images in every turn
3. **Budget limits**: Optional `--budget-usd` flag stops early

## Visualization

After a run, visualize the trajectory:

```bash
giant visualize trajectory.json
```

Shows:
- Thumbnail with all crop regions overlaid
- Step-by-step reasoning
- Final answer

## Implementation Reference

| Concept | File | Function/Class |
|---------|------|----------------|
| Agent loop | `agent/runner.py` | `GIANTAgent._navigation_loop` |
| Context | `agent/context.py` | `ContextManager` |
| Thumbnail | `wsi/reader.py` | `WSIReader.get_thumbnail` |
| Axis guides | `geometry/overlay.py` | `AxisGuideGenerator` |
| Cropping | `core/crop_engine.py` | `CropEngine.crop` |
| Level selection | `core/level_selector.py` | `PyramidLevelSelector` |

## Next Steps

- [LLM Integration](llm-integration.md) - How providers work
- [Prompt Design](../prompts/prompt-design.md) - Navigation prompts
- [Architecture](architecture.md) - System design
