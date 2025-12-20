# GIANT Prompt Design

> **Status**: Paper-derived (pending Supplementary Material verification)
>
> This document captures all prompt requirements extractable from the GIANT paper.
> When the authors release official prompts, we will compare and update.
>
> **Enhancement Note**: Section "2025 Pathology VLM Best Practices" contains domain
> enhancements beyond the paper. These are clearly marked and separable.

## Paper Evidence Summary

| Requirement | Source | Line | Confidence |
|-------------|--------|------|------------|
| Crop budget communicated | Algorithm 1 | 156 | High |
| Level-0 coordinate system | Sec 4.1 | 134 | High |
| Axis guides explained | Sec 4.1 | 134 | High |
| Output format (x, y, w, h) | Algorithm 1 | 159 | High |
| Final answer enforcement | Fig 5 caption | 200 | High |
| Reasoning per step | Algorithm 1 | 159 | High |
| Thumbnail size 1024px | Sec 4.2.1 | 183 | High |

---

## Required Prompt Components (High Confidence)

### 1. Crop Budget

**Evidence (Algorithm 1, line 156):**
```
P0 = {q, nav instructions + "at most T-1 crops"};
```

The initial prompt must tell the model how many crops it can make.

**Implementation:**
```
You have at most {max_steps - 1} crops to explore before providing your final answer.
```

### 2. Level-0 Coordinate System

**Evidence (Section 4.1, line 134):**
> "To orient the model, the thumbnail is overlaid with four evenly spaced axis guides along each dimension, labeled with absolute level-0 pixel coordinates."

The model must understand:
- Coordinates are absolute (Level-0 = full resolution)
- Axis guides show these coordinates visually
- All bounding boxes use this system

**Implementation:**
```
The image has AXIS GUIDES overlaid - red lines labeled with ABSOLUTE LEVEL-0 PIXEL COORDINATES.
All coordinates you output must use this Level-0 system (the slide's native resolution).
```

### 3. Bounding Box Output Format

**Evidence (Algorithm 1, line 159):**
```
(rt, at) ← LMM(C) ; // at = (x, y, w, h)
```

Each step produces reasoning + action, where action is a 4-tuple.

**Implementation:**
```json
{
  "reasoning": "I observe...",
  "action": {
    "type": "crop",
    "x": 10000,
    "y": 20000,
    "width": 5000,
    "height": 5000
  }
}
```

### 4. Final Answer Enforcement

**Evidence (Figure 5 caption, line 200):**
> "We use a system prompt to enforce that the model provide its final response after a specific number of iterations, marking a trial incorrect if the model exceeds this limit after 3 retries."

The prompt must explicitly require the model to answer on the final step.

**Implementation:**
```
On step {max_steps}, you MUST provide your final answer using the `answer` action.
```

### 5. Two Action Types

**Evidence (Algorithm 1 + Section 4.1):**
- `crop(x, y, w, h)`: Continue navigation
- `answer(text)`: Provide final response

**Implementation:**
```
Your available actions:
1. crop(x, y, width, height) - Zoom into a region for more detail
2. answer(text) - Provide your final answer to the question
```

---

## Inferred Components (Medium Confidence)

These are not explicitly stated but are strongly implied by the paper's methodology.

### 6. Pathology Domain Context

The paper tests on pathology slides. The model should know it's analyzing tissue.

**Implementation:**
```
You are analyzing a Whole Slide Image (WSI) - a gigapixel pathology slide.
```

### 7. Thumbnail vs Crop Distinction

Figure 4 shows the agent receives different image types:
- Initial: Low-resolution thumbnail (blurry)
- After crop: Higher-resolution region

**Implementation:**
```
The initial view is a low-resolution thumbnail. Cellular details require zooming in.
```

### 8. Iterative Refinement

Algorithm 1 shows a loop: observe → reason → act → observe...

**Implementation:**
```
At each step:
1. Analyze the current image
2. Explain your reasoning
3. Choose to crop (for more detail) or answer (if sufficient evidence)
```

---

## 2025 Pathology VLM Best Practices (Domain Enhancement)

> **Note**: This section contains enhancements derived from Dec 2025 literature review.
> These are NOT from the GIANT paper and can be removed for strict paper reproduction.

*Derived from literature search: "whole slide image LLM prompting 2025", "GPT-4V medical image navigation"*

1. **Anatomical Precision & Domain Vocabulary**
   - Insight: Generic "describe the image" prompts perform poorly.
   - Action: Use specific pathology terms (e.g., "stroma", "nuclei", "architecture", "mitotic figures") in the system prompt to prime the model's vocabulary.

2. **Hierarchical Observation (Multi-Scale)**
   - Insight: Pathologists scan low-power (architecture) before high-power (cellular details).
   - Action: Explicitly instruct the model to follow this "Architecture -> Cellular" observation flow.

3. **Visual Anchoring**
   - Insight: Models hallucinate less when forced to reference specific coordinates or visual markers.
   - Action: Reinforce the "Axis Guides" instruction and ask the model to cite coordinates in its reasoning.

4. **Role & Goal Specificity**
   - Insight: "You are a pathologist" is good, but "You are a pathologist diagnosing cancer grade" is better.
   - Action: Ensure the prompt adapts to the specific task type if known (e.g., QA vs Diagnosis).

### Gap Analysis (Current Implementation)

| Current State | Gap | Fix Applied |
|---------------|-----|-------------|
| Generic "Analyze image" | Lacks domain specificity | Added "Scan for architectural patterns, then cellular details" |
| "Provide reasoning" | Unstructured thought process | Enforced "Observation -> Reasoning -> Action" structure |
| "Low-res thumbnail" | Doesn't explain *why* zoom is needed | Explained "Low-res = Architecture only; High-res = Cellular" |
| No coordinate citing | Hallucination risk | Ask model to "Reference coordinates in reasoning" |

---

## What We Cannot Determine

Without the Supplementary Material, we cannot verify:

1. **Exact wording** - The precise phrases used
2. **Provider differences** - Whether OpenAI/Anthropic prompts differ
3. **Additional constraints** - Any rules not mentioned in the main text
4. **Retry instructions** - How the 3-retry policy is communicated
5. **Question formatting** - How the user's question is presented

---

## Current Implementation

See: `src/giant/prompts/templates.py`

Our templates implement all high-confidence requirements:
- Crop budget (Step X of Y, N crops remaining)
- Level-0 coordinate system (axis guides explanation)
- Bounding box format (crop action with x, y, width, height)
- Final answer enforcement (MUST use answer on final step)
- Two action types (crop, answer)

Plus domain enhancements (can be toggled off for strict reproduction):
- Hierarchical analysis workflow
- Pathology-specific vocabulary
- Coordinate referencing in reasoning

---

## Verification Plan

When Supplementary Material becomes available:

1. Compare official prompts to our templates
2. Document any differences
3. Update templates to match (or document intentional divergence)
4. Add regression tests for paper-required invariants
5. Decide whether to keep or remove domain enhancements

---

## References

- GIANT paper: `_literature/markdown/giant/giant.md`
  - Algorithm 1: lines 144-161
  - Section 4.1 (Axis guides): line 134
  - Figure 5 caption (step enforcement): line 200
  - Baseline thumbnail size: line 183
- Current implementation: `src/giant/prompts/templates.py`
- Bug tracking: `docs/bugs/BUG-020-placeholder-prompts.md`
- 2025 Literature: Web search "whole slide image LLM prompting 2025"
