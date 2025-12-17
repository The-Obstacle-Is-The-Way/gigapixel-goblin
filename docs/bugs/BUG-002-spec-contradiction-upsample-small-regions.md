# BUG-002: Spec Contradiction - Small Region Upsampling

## Severity: P2 (Medium Priority) - Spec-05.5 Doc Mismatch

## Status: Fixed (pending merge)

## Description

There is a **contradiction** between Spec-05.5's P1-3 test expectation and Spec-05 / the GIANT paper.

### The Contradiction

**Spec-05.5 Test P1-3:**
> "Tiny region (< target_size) - Request 100x100 L0 region with target_size=1000 - **Upsampled correctly, no artifacts**"

**Spec-05 Acceptance Criteria (line 15):**
> "Downsamples... (never upsample; if the read image is already ≤ S, return it unchanged)"

**Current Implementation (crop_engine.py:188-190):**
```python
# Never upsample: if image is smaller than target, return as-is
if original_long_side <= target_size:
    return image, 1.0
```

### Analysis

The current implementation correctly follows the **paper** and Spec-05: it never upsamples small regions. Spec-05.5’s P1-3 expected result is the incorrect part.

### Why the Paper Says "Never Upsample"

Upsampling pathology images introduces interpolation artifacts that can:
1. Create false texture patterns
2. Blur diagnostic features
3. Mislead the LLM about tissue structure

The LMM receives native resolution data, which is more accurate than interpolated data.

### Recommendation

Resolved by keeping the current implementation (paper-faithful) and updating Spec-05.5 P1-3 expected behavior:

**Current:** "Upsampled correctly, no artifacts"
**Updated:** "Returns native resolution unchanged (never upsample per Spec-05 / paper)"

### Code Location

- `src/giant/core/crop_engine.py` - `CropEngine._resize_to_target()`
- `docs/specs/spec-05.5-wsi-integration-checkpoint.md` - P1-3 test

### Testing Required

- Verify current test `test_region_smaller_than_target_no_upsample` passes ✓
- Verify current test `test_very_small_region` passes ✓
- Update Spec-05.5 expectation for P1-3 (doc-only)
