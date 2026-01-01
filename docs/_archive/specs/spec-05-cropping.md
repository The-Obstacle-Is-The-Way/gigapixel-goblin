# Spec-05: Image Cropping & Resampling Pipeline

## Overview
This specification implements the `CropRegion(W, at, S)` function defined in Algorithm 1. It orchestrates the `WSIReader` and `PyramidLevelSelector` to efficiently retrieve a region of interest, resize it to the exact target dimensions using high-quality resampling, and format it for consumption by the LMM (Base64).

## Dependencies
- [Spec-02: WSI Data Layer & OpenSlide Integration](./spec-02-wsi-data.md)
- [Spec-04: Pyramid Level Selection Algorithm](./spec-04-level-selection.md)

## Acceptance Criteria
- [ ] `CropEngine` class initialized with `WSIReader`.
- [ ] `crop` method accepts `Region` (L0) and `target_size` (S).
- [ ] Uses `PyramidLevelSelector` to pick the optimal read level.
- [ ] Reads the region using `WSIReader.read_region`.
- [ ] Downsamples the resulting image so the long side equals `S` (preserving aspect ratio) using `PIL.Image.Resampling.LANCZOS` (never upsample; if the read image is already ≤ `S`, return it unchanged).
- [ ] Returns a `CroppedImage` object containing the PIL image and its Base64 representation.
- [ ] Performance: Does not load full slide into memory.
- [ ] (Optional) Disk-backed caching (via `diskcache`) can memoize crops across runs (GIANT×N / benchmarks).

## Technical Design

### Data Models

```python
from dataclasses import dataclass
from PIL import Image

@dataclass
class CroppedImage:
    image: Image.Image
    base64_content: str
    original_region: Region  # The requested L0 region
    read_level: int         # The level it was read from
    scale_factor: float     # How much it was scaled after reading
```

### Implementation Details

#### `CropEngine.crop(region: Region, target_size: int = 1000)`
1.  **Level Selection:** Call `level_selector.select_level(region, metadata, target_size)`. Get `level_idx`.
2.  **Read:** Call `wsi_reader.read_region(location=(region.x, region.y), level=level_idx, size=(width_at_level, height_at_level))`.
    - Note: `size` passed to `read_region` must be calculated!
    - `width_at_level = region.width / downsample[level_idx]`
    - `height_at_level = region.height / downsample[level_idx]`
    - These must be cast to `int`.
3.  **Resize:**
    - If the read crop’s long side is **greater than** `target_size`, downsample to new dimensions maintaining aspect ratio such that `max(new_w, new_h) == target_size`.
    - Never upsample: if the read crop’s long side is **≤** `target_size`, return it unchanged.
    - `image.resize((new_w, new_h), resample=Image.Resampling.LANCZOS)`.
4.  **Encode:** Convert to Base64 (JPEG format, quality=85 default).

### Edge Cases
- **Aspect Ratio:** The region might be extremely wide or tall. The resize logic must handle this.
- **Rounding Errors:** When converting L0 dimension to Level-k dimension, flooring might lose a pixel. This is generally acceptable for LMM context, but we should be consistent.
- **Small Regions:** If the crop is smaller than `S` even at Level-0, do not upsample; return the native-resolution crop as-is.

### Optional: Crop Cache (diskcache)
For long benchmarks and majority-vote runs, enable an on-disk cache to avoid recomputing identical crops.
- Cache key: `(wsi_path, region.x, region.y, region.width, region.height, target_size, read_level)`
- Cache value: JPEG bytes (or base64) + metadata (`read_level`, `scale_factor`)
- Requirements:
  - Configurable cache directory and max size
  - Safe to disable (default off)

## Test Plan

### Unit Tests
1.  **End-to-End Flow:** Mock `WSIReaderProtocol` and `LevelSelectorProtocol`. Call `crop`. Verify:
    - `level_selector` was called.
    - `wsi_reader.read_region` was called with transformed coordinates/size.
    - Image was resized to `target_size`.
    - Base64 string is valid.
2.  **Resize Math:** Test the aspect ratio calculation separately.

## File Structure
```text
src/giant/core/
├── crop_engine.py
tests/unit/core/
└── test_crop_engine.py
```
