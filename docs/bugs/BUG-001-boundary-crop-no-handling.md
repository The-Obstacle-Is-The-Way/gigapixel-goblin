# BUG-001: Boundary Crop Has No Graceful Handling

## Severity: P3 (Low Priority) - Policy/Documentation

## Status: Open (Policy decision)

## Description

`CropEngine.crop()` does not clamp crop regions to slide bounds. If a region extends beyond the slide boundary, behavior is delegated to OpenSlide.

### Related Spec Tests
- **P1-1**: Boundary crop (right edge)
- **P1-2**: Boundary crop (bottom edge)

### Current Behavior

```python
# In crop_engine.py - NO bounds validation before read
raw_image = self._reader.read_region(
    location=(region.x, region.y),
    level=selected.level,
    size=region_size_at_level,
)
```

OpenSlide’s documented behavior for out-of-bounds reads is to return a full tile and pad any out-of-bounds pixels with transparency (RGBA). Since `WSIReader.read_region()` converts the returned image to RGB, padded pixels become black in the final crop.

### Expected Behavior (from Spec-05.5)

"Graceful handling (clamp or pad)" - The pipeline should either:
1. **Clamp** the region to slide bounds before reading, OR
2. **Pad** the result with a consistent background color

Current behavior already satisfies the “pad” option (black padding after RGBA→RGB conversion).

### Code Location

`src/giant/core/crop_engine.py:102-165` - `crop()` method

### Existing Infrastructure

The codebase already has `GeometryValidator.clamp_region()` in `src/giant/geometry/validators.py`, but Spec-09 places bounds validation at the agent layer (strict by default; clamp only as an explicit recovery path).

### Proposed Fix

Document and decide the policy explicitly:

- **Option A (keep current)**: Accept OpenSlide padding (black after conversion) and document it as the canonical behavior for out-of-bounds regions.
- **Option B (agent-level strict validation)**: In Spec-09, validate crops with `GeometryValidator.validate(...)` and re-prompt the LLM on invalid regions.
- **Option C (agent-level clamp recovery)**: In Spec-09, clamp only as an explicit, test-covered recovery path.

If we decide to clamp inside the crop pipeline (Option D), integrate `GeometryValidator.clamp_region()` into `CropEngine.crop()`:

```python
def crop(
    self,
    region: Region,
    target_size: int = 1000,
    bias: float = 0.85,
    jpeg_quality: int = 85,
) -> CroppedImage:
    # NEW: Validate/clamp region to slide bounds
    metadata = self._reader.get_metadata()
    bounds = Size(width=metadata.width, height=metadata.height)
    validator = GeometryValidator()
    clamped_region = validator.clamp_region(region, bounds)

    # Continue with clamped_region instead of region...
```

### Impact

- Without explicit documentation, engineers may assume out-of-bounds crops are errors or “undefined”.
- If we want strict bounds semantics, the policy belongs in Spec-09 (agent loop), not necessarily inside `CropEngine`.

### Testing Required

- Integration test (real file): Crop region extending past right/bottom edge and assert output size is preserved and padded area is black.
