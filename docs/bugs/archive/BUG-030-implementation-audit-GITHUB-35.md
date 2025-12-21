# BUG-030: Comprehensive Implementation Audit vs GIANT Paper

## Severity: P2 (Multiple Potential Issues)

## Status: Investigation Complete - Awaiting Senior Review

## Summary

A thorough codebase audit comparing our implementation against the GIANT paper has been conducted. This document catalogs all findings, both confirmed issues and verified-correct implementations, to establish a baseline for further investigation.

---

## Confirmed Issues

### ISSUE-1: Missing Paper Prompts (HIGH PRIORITY)

**Evidence from Paper:**
> "The system prompt used for OpenAI and Anthropic models is included in the Supplementary Material." (Section 4.1, line 142)

**Current Implementation:**
- `src/giant/prompts/templates.py` uses a custom prompt (lines 24-63)
- The prompt is labeled "Paper-derived (pending Supplementary Material verification)"
- We do NOT have access to the exact prompts from the Supplementary Material

**Impact:** Unknown - our prompts may differ significantly from what was used to achieve 32.3% accuracy.

**Status:** Needs Supplementary Material access or author contact.

---

### ISSUE-2: Prompt Format Differences (MEDIUM PRIORITY)

**Paper Specification (Algorithm 1):**
- Step 1 prompt: "nav instructions + at most T-1 crops" (line 156)
- Action format: `(rt, at) ← LMM(C)` where `at = (x, y, w, h)` (line 159)

**Current Implementation:**
Our prompt says:
```text
Navigation Budget: Step {step} of {max_steps}. You have at most {remaining_crops} crops remaining.
```

**Potential Issues:**
1. The paper says "at most T-1 crops" - we say "remaining_crops" which is `max_steps - step`
2. At step 1 with T=20, we show 19 remaining crops, which matches "T-1" ✓
3. However, the paper does NOT specify whether steps are 1-indexed or 0-indexed

**Impact:** Low - logic appears correct.

---

### ISSUE-3: TCGA-Specific Questions Format (HIGH PRIORITY)

**Paper (Figure 3):**
- TCGA: 30-way classification with "Balanced Accuracy" metric
- Questions appear to be simple prompts like "What is the primary diagnosis?"

**Current Implementation:**
- MultiPathQA provides per-row prompts and options in `data/multipathqa/MultiPathQA.csv`.
  - For `tcga` and `gtex`, the CSV prompt includes an `{options}` placeholder and explicitly
    asks for the **number of the correct option** (with an example JSON snippet like
    `{"answer": YOUR_ANSWER}`).
  - For `tcga_slidebench` and `tcga_expert_vqa`, the CSV prompt is usually just the question,
    so our loader appends a numbered options block and asks the model to respond with the
    1-based option index.

Example (TCGA):
```text
What is the primary diagnosis for this histopathology image?

Select from the following options:
1. Glioblastoma multiforme
2. Ovarian serous cystadenocarcinoma
...
30. Thymoma

Please choose the number of the correct option.
```

**Paper Evidence:**
- No explicit evidence of how options were presented
- SlideChat paper uses similar multiple-choice format

**Impact:** Medium - format may affect model reasoning.

---

### ISSUE-4: Claude Image Size (CONFIRMED CORRECT)

**Paper (Table 1, footnote):**
> "Due to pricing differences with the Claude API for images, we provided cropped images as 500 px instead of 1000 px."

**Current Implementation:**
- `src/giant/config.py:79`: `IMAGE_SIZE_ANTHROPIC: int = 500` ✓

**Status:** CORRECT

---

### ISSUE-5: Thumbnail Size (MEDIUM PRIORITY)

**Paper Evidence:**
- Figure 2 caption: "In the thumbnail setting, the model receives a 1024×1024 px image"
- Section 4.1: "overlaid with four evenly spaced axis guides"

**Current Implementation:**
- `src/giant/config.py:65`: `THUMBNAIL_SIZE: int = 1024` ✓
- `src/giant/geometry/overlay.py`: Adds axis guides ✓

**Status:** CORRECT

---

### ISSUE-6: Crop Target Size (NEEDS VERIFICATION)

**Paper (Section 4.1, line 136):**
> "We choose the pyramid level that will render the crop to a target long side (default S=1000 px)"

**Current Implementation:**
- `src/giant/config.py:62`: `WSI_LONG_SIDE_TARGET: int = 1000` ✓
- `src/giant/config.py:78`: `IMAGE_SIZE_OPENAI: int = 1000` ✓

**However:**
- For Anthropic, crops are 500px per IMAGE_SIZE_ANTHROPIC
- This matches the paper footnote

**Status:** CORRECT

---

### ISSUE-7: Oversampling Bias (CONFIRMED CORRECT)

**Paper (Section 4.1, line 136):**
> "biasing toward finer levels (oversampling bias 0.85)"

**Current Implementation:**
- `src/giant/config.py:64`: `OVERSAMPLING_BIAS: float = 0.85` ✓
- `src/giant/core/level_selector.py`: Implements bias correctly ✓

**Status:** CORRECT

---

### ISSUE-8: Navigation Steps T=20 (FIXED in BUG-029)

**Paper (Section 5.2, line 214):**
> "Across datasets, we found that the best-performing configuration used T = 20."

**Current Implementation (after fix):**
- `src/giant/agent/runner.py:129`: `max_steps: int = 20` ✓

**Status:** FIXED

---

### ISSUE-9: Bootstrap Replicates (CONFIRMED CORRECT)

**Paper (Table 1):**
> "Std. dev. from 1000 bootstrap replicates"

**Current Implementation:**
- `src/giant/config.py:72`: `BOOTSTRAP_REPLICATES: int = 1000` ✓

**Status:** CORRECT

---

### ISSUE-10: Patch Baseline Configuration (CONFIRMED CORRECT)

**Paper (Section 4.2.1, line 184):**
> "Following SlideChat [8], we sample 30 random 224×224 patches"

**Current Implementation:**
- `src/giant/vision/constants.py`: `N_PATCHES: int = 30` ✓
- `src/giant/vision/constants.py`: `PATCH_SIZE: int = 224` ✓

**Status:** CORRECT

---

## Potential Issues Requiring Further Investigation

### INVESTIGATE-1: Answer Extraction Logic

**Observation:**
The trajectory shows the model outputting `{"answer": 14}` for melanoma.

**Current Extraction:**
- `src/giant/eval/answer_extraction.py` looks for integers in text
- The JSON answer format `{"answer": 14}` is parsed correctly

**But:**
- The paper doesn't specify expected answer format
- We force JSON output via structured output schema
- This may differ from how the paper evaluated responses

**Recommendation:** Verify answer extraction matches paper methodology.

---

### INVESTIGATE-2: Axis Guide Implementation

**Paper:**
> "four evenly spaced axis guides along each dimension, labeled with absolute level-0 pixel coordinates"

**Current Implementation:**
- `src/giant/geometry/overlay.py` draws axis guides

**Concern:**
- Are our axis guides matching exactly what the paper used?
- Font size, color, positioning could affect LLM's ability to read coordinates

**Recommendation:** Visual comparison with paper figures needed.

---

### INVESTIGATE-3: CLAM Pipeline for Baselines

**Paper (Section 4.2.1):**
> "we use the CLAM Python package to segment the tissue on the slide before patching"

**Current Implementation:**
- `src/giant/vision/segmentation.py` uses custom Otsu-based segmentation
- Does NOT use CLAM package

**Impact:** For GIANT mode, this is irrelevant (we don't use CLAM).
For baseline modes (thumbnail/patch), results may differ.

**Recommendation:** Verify if custom segmentation is equivalent to CLAM.

---

### INVESTIGATE-4: Model Temperature/Sampling

**Paper:** No mention of temperature settings.

**Current Implementation:**
- Temperature not explicitly set in LLM clients
- Defaults to provider defaults

**Recommendation:** Verify paper used default temperature or specify.

---

### INVESTIGATE-5: Early Stopping

**Paper (Algorithm 1):**
> "repeating until a step limit T or early stop"

**Current Implementation:**
- Agent stops when model outputs `answer()` action
- This matches paper behavior

**Status:** Likely CORRECT

---

## Verified Correct Implementations

| Component | Paper Spec | Implementation | Status |
|-----------|------------|----------------|--------|
| Max steps (T) | 20 | `max_steps=20` | ✓ Fixed |
| Crop size OpenAI (S) | 1000px | `IMAGE_SIZE_OPENAI=1000` | ✓ |
| Crop size Anthropic | 500px | `IMAGE_SIZE_ANTHROPIC=500` | ✓ |
| Thumbnail size | 1024px | `THUMBNAIL_SIZE=1024` | ✓ |
| Oversampling bias | 0.85 | `OVERSAMPLING_BIAS=0.85` | ✓ |
| Bootstrap replicates | 1000 | `BOOTSTRAP_REPLICATES=1000` | ✓ |
| Patch size (baseline) | 224px | `PATCH_SIZE=224` | ✓ |
| Patch count (baseline) | 30 | `N_PATCHES=30` | ✓ |
| Lanczos resampling | Yes | PIL Lanczos | ✓ |
| Balanced accuracy | TCGA/PANDA/GTEx | Implemented | ✓ |

---

## Recommendations

### Immediate Actions (Before More Testing)

1. **Get Supplementary Material**: Contact paper authors or find supplementary material for exact prompts used.

2. **Verify Answer Format**: Confirm the paper's expected answer format matches our JSON schema.

3. **Run Full TCGA Benchmark**: With T=20 fixed, run full 221-item TCGA benchmark to compare against paper's 32.3%.

### Medium-Term Actions

4. **Axis Guide Audit**: Compare our axis guide rendering with paper figures visually.

5. **CLAM Integration**: Consider adding CLAM segmentation for baseline mode parity.

6. **Temperature Testing**: Test with explicit temperature=0 for reproducibility.

---

## Test Commands for Validation

```bash
# Run TCGA benchmark with T=20 (paper configuration)
giant benchmark tcga --max-items=50 --provider=openai --model=gpt-5.2

# Expected: ~32% balanced accuracy (paper reports 32.3% ± 3.5%)
# Current: 0% on small samples (need larger sample)

# Run with verbose logging to verify prompts
GIANT_LOG_LEVEL=DEBUG giant run /path/to/tcga/slide.svs -q "What is the diagnosis?"
```

---

## References

- GIANT Paper: "Navigating Gigapixel Pathology Images with Large Multimodal Models"
- Paper Section 4.1: Algorithm details
- Paper Section 5.2: Performance scaling with iterations
- Paper Table 1: Benchmark results
- Paper Footnote Table 1: Claude 500px image size

---

## Conclusion

The implementation appears largely faithful to the paper specifications. The main concerns are:

1. **Prompts**: We don't have access to the exact prompts used in the paper.
2. **Sample Size**: Our tests used tiny samples (1-5 items) vs paper's full benchmarks.
3. **Model Versions**: Paper used "GPT-5" - we use `gpt-5.2` which should be equivalent or better.

**Next Step**: Run full TCGA benchmark (221 items) with T=20 to validate accuracy matches paper's 32.3%.
