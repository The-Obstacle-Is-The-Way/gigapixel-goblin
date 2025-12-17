# BUG-001: Boundary Crop Has No Graceful Handling

## Severity: P1 (High Priority)

## Status: Open

## Description

The `CropEngine.crop()` method does not validate that the requested region is within slide bounds. When a region extends beyond the slide boundary (right edge or bottom edge), the behavior is undefined - it relies entirely on OpenSlide's behavior.

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

OpenSlide behavior for out-of-bounds reads varies by vendor and may:
- Return black/transparent pixels for OOB areas (Aperio)
- Return partial image
- Raise an exception

### Expected Behavior (from Spec-05.5)

"Graceful handling (clamp or pad)" - The pipeline should either:
1. **Clamp** the region to slide bounds before reading, OR
2. **Pad** the result with a consistent background color

### Code Location

`src/giant/core/crop_engine.py:102-165` - `crop()` method

### Existing Infrastructure

The codebase already has `GeometryValidator.clamp_region()` in `src/giant/geometry/validators.py:92-140` which can clamp regions to bounds. This is currently **unused** in the crop pipeline.

### Proposed Fix

Integrate `GeometryValidator.clamp_region()` into `CropEngine.crop()`:

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

- LLM requests for regions at slide edges will fail unpredictably
- Agent loop may get stuck on boundary regions
- Error messages will be confusing (vendor-specific)

### Testing Required

- Unit test: Crop region extending past right edge
- Unit test: Crop region extending past bottom edge
- Unit test: Crop region entirely outside bounds
- Integration test with real SVS file at boundary
