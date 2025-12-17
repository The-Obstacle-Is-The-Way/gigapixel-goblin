# Spec-03: Coordinate System & Geometry

## Overview
This specification defines the core geometry primitives and coordinate systems used by GIANT. The paper specifies that all navigation occurs in **Level-0 (absolute pixel) coordinates**. This module provides robust types for handling these coordinates, verifying they are within image bounds, and generating the visual "axis guides" overlaid on thumbnails to help the LLM orient itself.

## Dependencies
- [Spec-02: WSI Data Layer & OpenSlide Integration](./spec-02-wsi-data.md)

## Acceptance Criteria
- [ ] `Point`, `Size`, and `Region` Pydantic models are implemented with integer fields.
- [ ] `Region` supports conversion to/from `(x, y, w, h)` tuples.
- [ ] `GeometryValidator` class exists to check if a `Region` is valid within a given `WSIMetadata`.
- [ ] `AxisGuideGenerator` creates a transparent overlay with 4 evenly spaced grid lines/labels per dimension.
- [ ] `OverlayService` combines the thumbnail and axis guides into a single image for the LLM.
- [ ] Coordinate transformation utilities (Level-N <-> Level-0) are implemented and tested.

## Technical Design

### Data Models

```python
from pydantic import BaseModel, Field

class Point(BaseModel):
    x: int = Field(..., ge=0)
    y: int = Field(..., ge=0)

class Size(BaseModel):
    width: int = Field(..., gt=0)
    height: int = Field(..., gt=0)

class Region(BaseModel):
    """Represents a rectangular region (x, y, w, h) in Level-0 coordinates."""
    x: int = Field(..., ge=0)
    y: int = Field(..., ge=0)
    width: int = Field(..., gt=0)
    height: int = Field(..., gt=0)

    @property
    def area(self) -> int:
        return self.width * self.height

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height
```

### Implementation Details

#### Coordinate Systems
- **Level-0:** The "Ground Truth" absolute pixel coordinates. All `Region` objects are Level-0 by default.
- **Thumbnail Space:** The coordinates on the downsampled thumbnail.
- **Transformation:**
  - `Thumbnail -> Level-0`: `coord_L0 = coord_thumb * downsample_factor`
  - `Level-0 -> Thumbnail`: `coord_thumb = coord_L0 / downsample_factor`

#### Axis Guides Implementation
The paper states: "Thumbnail is overlaid with four evenly spaced axis guides along each dimension, labeled with absolute level-0 pixel coordinates."

**Algorithm:**
1.  Input: `thumbnail_image`, `wsi_metadata`.
2.  Calculate step size: `step_x = thumbnail_width / 5`, `step_y = thumbnail_height / 5` (to get 4 internal lines).
3.  Draw lines:
    - Vertical lines at `x = step_x * i` for `i in 1..4`.
    - Horizontal lines at `y = step_y * i` for `i in 1..4`.
4.  Draw Labels:
    - Calculate the corresponding Level-0 coordinate for each line: `L0_x = x * (wsi_width / thumbnail_width)`.
    - Render text label (e.g., "15000") near the edge of the line.
5.  Style: Semi-transparent red or contrasting color to be visible but not obscure tissue.

### Validation
`GeometryValidator.validate(region: Region, bounds: Size)`:
- Checks if `region.right <= bounds.width` and `region.bottom <= bounds.height`.
- Raises a `ValidationError` if out of bounds (strict by default).

#### Optional Clamping (Explicit Recovery Path)
GIANT paper does not specify how invalid crops are handled. For robustness, implement clamping as a **separate** method (`clamp_region`) and only use it when explicitly chosen by the agent error-recovery policy (Spec-09).

#### `GeometryValidator.clamp_region`
```python
def clamp_region(self, region: Region, bounds: Size) -> Region:
    """Clamp region to valid bounds (common LLM error recovery).

    Ensures:
    - x, y are within [0, bounds-1]
    - width, height respect the clamped origin
    - Minimum dimension of 1px is preserved
    """
    clamped_x = max(0, min(region.x, bounds.width - 1))
    clamped_y = max(0, min(region.y, bounds.height - 1))
    clamped_w = max(1, min(region.width, bounds.width - clamped_x))
    clamped_h = max(1, min(region.height, bounds.height - clamped_y))
    return Region(x=clamped_x, y=clamped_y, width=clamped_w, height=clamped_h)
```

## Test Plan

### Unit Tests
1.  **Region Math:** Test `right`, `bottom`, `area` properties.
2.  **Validation:** Test `validate` with inside, outside, and overlapping regions.
3.  **Clamping:** Test `clamp_region` with edge cases:
    - Region fully inside bounds → unchanged
    - Region x/y exceeds bounds → clamped to edge
    - Region width/height exceeds remaining space → truncated
    - Region entirely outside bounds → clamped to corner with 1px
4.  **Transformation:** Test converting coordinates between Level-0 and arbitrary downsamples.
5.  **Overlay Generation:** Use a blank image, run `AxisGuideGenerator`, and verify (via pixel inspection or mock calls) that lines are drawn at correct intervals.

### Property-Based Tests
- Generate random valid `Region`s and `WSIMetadata`. Verify that transforming L0 -> LN -> L0 returns the original coordinate (within rounding error margin).

## File Structure
```text
src/giant/geometry/
├── __init__.py
├── primitives.py   # Point, Size, Region
├── validators.py   # Bounds checking
├── transforms.py   # Coordinate transforms
└── overlay.py      # Axis guide rendering
tests/unit/geometry/
├── test_primitives.py
└── test_overlay.py
```

## API Reference
N/A
