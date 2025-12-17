# BUG-002: Spec Contradiction - Small Region Upsampling

## Severity: P1 (High Priority) - Spec Ambiguity

## Status: Open - Requires Design Decision

## Description

There is a **contradiction** between Spec-05.5's P1-3 test expectation and the algorithm invariant defined in Spec-05 and the GIANT paper.

### The Contradiction

**Spec-05.5 Test P1-3:**
> "Tiny region (< target_size) - Request 100x100 L0 region with target_size=1000 - **Upsampled correctly, no artifacts**"

**Spec-05 Acceptance Criteria (line 15):**
> "Downsamples... (never upsample; if the read image is already ≤ S, return it unchanged)"

**Algorithm Invariant (level_selector.py:14-16):**
> "After level selection, we always downsample (or 1:1) to reach target_size, **never upsample**, unless the region is smaller than target_size at Level-0."

**Current Implementation (crop_engine.py:188-190):**
```python
# Never upsample: if image is smaller than target, return as-is
if original_long_side <= target_size:
    return image, 1.0
```

### Analysis

The current implementation correctly follows the **paper algorithm** - it never upsamples small regions. However, Spec-05.5 expects upsampling to `target_size=1000`.

### Why the Paper Says "Never Upsample"

Upsampling pathology images introduces interpolation artifacts that can:
1. Create false texture patterns
2. Blur diagnostic features
3. Mislead the LLM about tissue structure

The LMM receives native resolution data, which is more accurate than interpolated data.

### Design Decision Required

**Option A: Follow Paper (Current Implementation)**
- Pros: No interpolation artifacts, accurate data for LLM
- Cons: Small regions may be hard for LLM to analyze (few pixels)

**Option B: Upsample Small Regions**
- Pros: Consistent input size for LLM, easier to display
- Cons: Introduces artifacts, violates paper algorithm

**Option C: Conditional Upsample with Warning**
- Add optional `allow_upsample=False` parameter
- Log warning when upsampling occurs
- LLM prompt can request native size

### Recommendation

**Keep current implementation (Option A)** - it follows the paper algorithm. Update Spec-05.5 P1-3 test expectation:

**Current:** "Upsampled correctly, no artifacts"
**Updated:** "Returns native resolution unchanged (never upsample per paper invariant)"

### Code Location

- `src/giant/core/crop_engine.py:167-211` - `_resize_to_target()`
- `docs/specs/spec-05.5-wsi-integration-checkpoint.md:43` - P1-3 test

### Testing Required

- Verify current test `test_region_smaller_than_target_no_upsample` passes ✓
- Verify current test `test_very_small_region` passes ✓
- Update Spec-05.5 expectation for P1-3
