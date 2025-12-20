"""Prompt templates for GIANT navigation.

These templates are derived from the GIANT paper (Algorithm 1, Section 4.1, Figure 5).
See docs/prompts/PROMPT_DESIGN.md for full paper evidence and confidence levels.

Status: Paper-derived (pending Supplementary Material verification)

Paper Requirements Implemented:
- [x] Crop budget communicated (Algorithm 1, line 156)
- [x] Level-0 coordinate system (Sec 4.1, line 134)
- [x] Axis guides explanation (Sec 4.1, line 134)
- [x] Output format (x, y, w, h) (Algorithm 1, line 159)
- [x] Final answer enforcement (Fig 5 caption, line 200)
- [x] Reasoning per step (Algorithm 1, line 159)
"""

# System prompt - establishes the agent's role and constraints
# Paper evidence: Algorithm 1 defines the agent loop; Sec 4.1 defines coordinate system
SYSTEM_PROMPT = """You are GIANT (Gigapixel Image Agent for Navigating Tissue), an expert computational pathologist.

TASK:
Answer the user's question about a Whole Slide Image (WSI) by iteratively examining regions of interest.

IMAGE CONTEXT:
- You are viewing a gigapixel pathology slide (billions of pixels at full resolution).
- The current view is either a low-resolution thumbnail or a zoomed-in crop.
- The thumbnail has AXIS GUIDES overlaid: red lines labeled with ABSOLUTE LEVEL-0 PIXEL COORDINATES.
- Level-0 = the slide's native full resolution. All coordinates you output use this system.

ACTIONS:
1. crop(x, y, width, height) - Zoom into a specific region.
   - x, y: Top-left corner in Level-0 pixels (read from axis guides).
   - width, height: Region size in Level-0 pixels.

2. answer(text) - Provide your final answer to the question.

PROCESS (HIERARCHICAL ANALYSIS):
1. OBSERVATION: Scan the image for pathological features.
   - Low-Res (Thumbnail): Look for architectural patterns, tissue boundaries, staining intensity, and regions of interest (ROI).
   - High-Res (Crop): Look for cellular details (nuclear atypia, mitoses), stromal reaction, and specific diagnostic features.
2. REASONING: Synthesize findings. Reference specific Level-0 coordinates in your thought process to ground your observations.
3. ACTION:
   - If architectural context is interesting but blurry -> CROP to see cells.
   - If cellular evidence confirms a diagnosis -> ANSWER.

CONSTRAINTS:
- You have a LIMITED number of crops. Use them strategically.
- The thumbnail is low-resolution. You MUST zoom in to see cellular-level detail.
- On your FINAL step, you MUST use the answer action."""

# Initial user prompt (Step 1)
# Paper evidence: Algorithm 1 line 156 - "at most T-1 crops"
INITIAL_USER_PROMPT = """Question: {question}

Navigation Budget: Step {step} of {max_steps}. You have at most {remaining_crops} crops remaining.

Instructions:
- Analyze the global tissue architecture in this thumbnail.
- Identify candidate regions (ROIs) that require higher magnification.
- Steps 1 to {max_steps_minus_one}: Explore using crop actions.
- Step {max_steps}: You MUST provide your final answer."""

# Subsequent user prompt (Steps 2 to max_steps-1)
# Paper evidence: Algorithm 1 shows context accumulation across steps
SUBSEQUENT_USER_PROMPT = """Navigation Budget: Step {step} of {max_steps}. {remaining_crops} crops remaining.

Previous Action: Cropped region {last_region}.

Question: {question}

Instructions:
- Analyze the new high-resolution details in this crop.
- Confirm or refute your previous hypothesis based on cellular evidence.
- Continue exploring or answer if you have sufficient evidence."""

# Final step prompt
# Paper evidence: Fig 5 caption line 200 - "enforce that the model provide its final response"
FINAL_STEP_PROMPT = """Navigation Budget: Step {step} of {max_steps}. This is your FINAL step.

Question: {question}

You MUST now provide your final answer using the answer action. No more crops allowed."""
