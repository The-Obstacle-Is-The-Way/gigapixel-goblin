# Spec-11: CLAM Integration (Patch Baseline)

## Overview
This specification covers the tissue segmentation + random patch sampling needed to reproduce the paper's **"Random Patch" baseline**: segment tissue (CLAM-style), sample 30 random 224×224 patches from tissue, run the LMM independently per patch, and aggregate by majority vote.

**Paper Reference:** "Following prior work, we use the CLAM Python package to segment the tissue on the slide before patching. [...] The model independently answers each patch, and predictions are combined by majority vote."

**Implementation Choice (Paper Fidelity vs. Portability):**
- **Primary (paper-faithful):** Use the CLAM pipeline for tissue segmentation when available.
- **Fallback (portable):** Use a documented "CLAM-parity" reimplementation with fixed parameters for environments where CLAM is not installable.

## Dependencies
- [Spec-02: WSI Data Layer & OpenSlide Integration](./spec-02-wsi-data.md)

## Acceptance Criteria
- [x] `TissueSegmentor` supports `backend={"clam","parity"}` (both run the CLAM-parity implementation; the `clam` name is reserved for future optional external CLAM integration).
- [x] Produces a binary mask (Tissue/Background) from the WSI thumbnail.
- [x] Implements Otsu's thresholding + morphological closing (CLAM default behavior).
- [x] `RandomPatchSampler` implemented: Returns `N=30` random `Region`s (Level-0 coords) of size `PATCH_SIZE=224×224` whose center overlaps tissue mask.
- [x] **Determinism:** RNG seeding via `seed` parameter for reproducible sampling.
- [x] **Majority vote aggregation:** `aggregate_predictions(predictions: list[str]) -> str` with deterministic tie-breaking (alphabetical).
- [x] Dependencies `opencv-python`, `scipy`, and `scikit-image` verified in `pyproject.toml`.

## Technical Design

### Implementation Details

#### Tissue Segmentation
1.  **Get Thumbnail:** Load WSI thumbnail (Level roughly corresponding to 32x downsample or fixed size).
2.  **Color Space:** Convert to HSV.
3.  **Threshold:** Apply Otsu thresholding on the Saturation channel (common for H&E) or simply luminance filtering to remove white background.
4.  **Refine:** Use `cv2.morphologyEx` (Close) to fill small holes.
5.  **Contours:** Find contours to get bounding boxes of tissue chunks.

#### Random Sampler (Paper-Faithful)

**Paper Parameters:**
- `N = 30` patches per slide
- `PATCH_SIZE = 224×224` pixels (Level-0)

**Patch Image Construction (Baseline):**
- Each sampled `Region` is read directly via `WSIReader.read_region(..., level=0, size=(224,224))`.
- No additional resizing is applied (the model receives exactly 224×224 px images, per paper).

**Algorithm:**
```python
def sample_patches(
    mask: np.ndarray,  # Binary tissue mask at thumbnail scale
    wsi_metadata: WSIMetadata,
    n_patches: int = 30,
    patch_size: int = 224,
    seed: int = 42,
) -> list[Region]:
    """Sample N random patches from tissue regions."""
    rng = np.random.default_rng(seed)

    # Scale factor: thumbnail → Level-0
    scale_x = wsi_metadata.width / mask.shape[1]
    scale_y = wsi_metadata.height / mask.shape[0]

    # Find all tissue pixel coordinates
    tissue_coords = np.argwhere(mask > 0)  # (y, x) format
    if len(tissue_coords) == 0:
        raise ValueError("No tissue detected in slide")

    patches = []
    attempts = 0
    max_attempts = n_patches * 100

    while len(patches) < n_patches and attempts < max_attempts:
        # Random tissue pixel
        idx = rng.integers(len(tissue_coords))
        ty, tx = tissue_coords[idx]

        # Convert to Level-0 coordinates (center of patch)
        cx = int(tx * scale_x)
        cy = int(ty * scale_y)

        # Compute patch bounds
        x = cx - patch_size // 2
        y = cy - patch_size // 2

        # Ensure within bounds
        x = max(0, min(x, wsi_metadata.width - patch_size))
        y = max(0, min(y, wsi_metadata.height - patch_size))

        patches.append(Region(x=x, y=y, width=patch_size, height=patch_size))
        attempts += 1

    return patches
```

#### Majority Vote Aggregation

```python
from collections import Counter

def aggregate_predictions(predictions: list[str]) -> str:
    """Majority vote with deterministic tie-breaking (alphabetical)."""
    if not predictions:
        raise ValueError("No predictions to aggregate")

    counts = Counter(predictions)
    max_count = max(counts.values())

    # All predictions with max count (handle ties)
    winners = [pred for pred, count in counts.items() if count == max_count]

    # Deterministic tie-break: alphabetical order
    return sorted(winners)[0]
```

## Test Plan

### Unit Tests
1.  **Segmentation Mask:** Test that tissue regions produce True, background False.
2.  **Morphological Closing:** Verify small holes are filled.
3.  **Random Sampler:** Test that N patches are returned and all fall within tissue mask.
4.  **Edge Cases:** Empty slide (all background), fully filled slide.

## File Structure
```text
src/giant/vision/
├── __init__.py
├── segmentation.py   # TissueSegmentor, tissue_mask_from_thumbnail
├── sampler.py        # RandomPatchSampler, sample_patches()
├── aggregation.py    # aggregate_predictions() for majority vote
└── constants.py      # N_PATCHES=30, PATCH_SIZE=224, HSV thresholds

tests/unit/vision/
├── test_segmentation.py
├── test_sampler.py
└── test_aggregation.py
```
