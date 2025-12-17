# BUG-003: Huge Region Has No Memory Protection

## Severity: P1 (High Priority)

## Status: Open

## Description

The `CropEngine.crop()` method has no protection against extremely large region requests that could exhaust memory. A request for the entire slide dimensions could attempt to load gigabytes of pixel data into RAM.

### Related Spec Tests

- **P1-4**: Huge region (entire slide) - "Request full slide dimensions - Falls back to thumbnail or errors gracefully"

### Current Behavior

```python
# In crop_engine.py - No size limit check
raw_image = self._reader.read_region(
    location=(region.x, region.y),
    level=selected.level,
    size=region_size_at_level,
)
```

For a 100,000 x 80,000 pixel slide at Level-0:
- Uncompressed RGB: `100000 * 80000 * 3 = 24 GB`

Even at Level-2 (16x downsample), reading a full slide:
- Size: `6250 x 5000 = 31.25 million pixels`
- Uncompressed: `~94 MB`

The level selector may pick Level-2 for `target_size=1000`, but the read still allocates significant memory before resize.

### Expected Behavior (from Spec-05.5)

"Falls back to thumbnail or errors gracefully"

### Proposed Fix

Add a configurable maximum read dimension check:

```python
# Constants
_MAX_READ_DIMENSION = 10000  # Max pixels per dimension for safety

def crop(self, region: Region, ...) -> CroppedImage:
    # ... level selection ...

    region_size_at_level = size_at_level(
        (region.width, region.height), selected.downsample
    )

    # NEW: Safety check for huge regions
    if max(region_size_at_level) > _MAX_READ_DIMENSION:
        raise ValueError(
            f"Region too large: {region_size_at_level}. "
            f"Maximum dimension is {_MAX_READ_DIMENSION}px. "
            f"Use get_thumbnail() for full-slide overview."
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

- Unit test: Request entire slide dimensions, verify error/fallback
- Unit test: Request moderately large region (5000x5000), verify success
- Memory profiling test: Verify peak memory stays bounded
