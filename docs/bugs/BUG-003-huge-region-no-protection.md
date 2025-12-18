# BUG-003: Huge Region Has No Memory Protection

## Severity: P1 (High Priority)

## Status: **Fixed**

## Description

The `CropEngine.crop()` method has no protection against extremely large region requests that could exhaust memory. A request for the entire slide dimensions could attempt to load gigabytes of pixel data into RAM.

### Related Spec Tests

- **P1-4**: Huge region (entire slide) - "Request full slide dimensions - Falls back to thumbnail or errors gracefully"

### Current Behavior

```python
# In crop_engine.py - Guardrail prevents extreme reads
region_size_at_level = size_at_level(
    (region.width, region.height), selected.downsample
)
if max(region_size_at_level) > effective_max:
    raise ValueError(
        "Region too large ... Use a smaller region or get_thumbnail() ..."
    )
```

`openslide.read_region` allocates an **RGBA** buffer (4 bytes/pixel) for `w*h` pixels *before* any resizing. `WSIReader.read_region()` then converts RGBA → RGB, which can transiently duplicate memory.

For a 100,000 × 80,000 pixel slide at Level-0:
- Uncompressed RGBA: `100000 * 80000 * 4 ≈ 32 GB` (plus overhead)

Even at 16× downsample (if that’s the coarsest available), reading a full slide:
- Size: `6250 × 5000 = 31.25M pixels`
- Uncompressed RGBA: `~125 MB` (plus overhead)

The level selector will usually pick a coarse level to keep the crop near the biased target size, but **worst cases exist**:
- Slides with few pyramid levels (small max downsample)
- Single-level slides (`level_count=1`)
- Very large regions (near full-slide) combined with small max downsample

### Expected Behavior (from Spec-05.5)

"Falls back to thumbnail or errors gracefully"

### Proposed Fix

Implemented: configurable maximum read dimension check.

```python
_DEFAULT_MAX_READ_DIMENSION = 10000

def crop(..., max_read_dimension: int | None = None) -> CroppedImage:
    # ...
    effective_max = _DEFAULT_MAX_READ_DIMENSION if max_read_dimension is None else max_read_dimension
    if effective_max > 0 and max(region_size_at_level) > effective_max:
        raise ValueError(
            f"Region too large: {w}x{h} pixels at level {selected.level} "
            f"exceeds maximum dimension {effective_max}px. "
            "Use a smaller region or get_thumbnail() for full-slide overview."
        )
```

### Alternative: Automatic Thumbnail Fallback

For full-slide requests, automatically fall back to `reader.get_thumbnail()`:

```python
if (region.width == metadata.width and
    region.height == metadata.height):
    # Full slide requested - use thumbnail
    thumb = self._reader.get_thumbnail((target_size, target_size))
    # ... encode and return
```

### Code Location

`src/giant/core/crop_engine.py:102-165` - `crop()` method

### Impact

- OOM (Out of Memory) errors on large region requests
- Process crashes without meaningful error message
- LLM cannot recover from crash (no guidance on what went wrong)

### Testing Required

Implemented:

- Unit tests verify:
  - default rejection (>10000px at selected level)
  - custom limit via `max_read_dimension`
  - disabling via `max_read_dimension=0` (for property tests)
  - error message includes actual dimensions
