# BUG-010: MPP (Microns Per Pixel) Is Nullable With No Guards

## Severity: P3 (Low Priority) - Future-Proofing

## Status: ARCHIVED (2025-12-19) - Not an active bug

## Archive Reason

This is not an active bug. Per the original description: "Today, no production code uses MPP values, so there is no active bug."

This document serves as a **future-proofing reminder** for when physical-unit features are implemented. The nullable `mpp_x`/`mpp_y` fields are correct by design (many slides lack calibration data). The mitigation patterns below should be applied when physical measurements are added.

---

## Description

`WSIMetadata.mpp_x` and `mpp_y` are `float | None` to support slides without calibration data. This is correct. Today, no production code uses MPP values, so there is no active bug — this is a reminder to handle `None` safely once physical-unit features are implemented.

### Current Code

```python
# src/giant/wsi/types.py:45-46
@dataclass(frozen=True)
class WSIMetadata:
    # ...
    mpp_x: float | None   # ← Can be None
    mpp_y: float | None   # ← Can be None
```

### The Time Bomb

When Spec-XX implements physical distance calculations (e.g., measuring tumor size):

```python
# Future code
def measure_physical_size(region: Region, metadata: WSIMetadata) -> float:
    """Calculate physical size in millimeters."""
    # THIS WILL CRASH when mpp_x is None
    width_mm = region.width * metadata.mpp_x / 1000  # TypeError: unsupported operand
```

### Current Usage

The current codebase doesn't use MPP for calculations. It becomes relevant when:
1. Physical measurements are added (Spec-XX)
2. User opens a slide without MPP data (common for TIFF files)
3. Code tries to multiply by `None`

### Evidence in Tests

```python
# tests/unit/wsi/test_types.py:81-95
def test_metadata_with_none_mpp(self) -> None:
    """Test metadata can be created with None MPP values."""
    metadata = WSIMetadata(
        # ...
        mpp_x=None,  # ← Test proves None is valid
        mpp_y=None,
    )
    assert metadata.mpp_x is None  # ← But no test for USING None safely
```

### Expected Pattern

```python
def measure_physical_size(region: Region, metadata: WSIMetadata) -> float | None:
    """Calculate physical size in millimeters, or None if uncalibrated."""
    if metadata.mpp_x is None or metadata.mpp_y is None:
        logger.warning(
            "Slide has no MPP calibration data. Physical measurements unavailable.",
            path=metadata.path,
        )
        return None

    width_mm = region.width * metadata.mpp_x / 1000
    # ...
```

### Slides Without MPP

| Vendor | MPP Available | Notes |
|--------|---------------|-------|
| Aperio (.svs) | Usually yes | Stored in properties |
| Hamamatsu (.ndpi) | Usually yes | Stored in properties |
| Generic TIFF | Usually NO | No standard metadata |
| DICOM | Yes | In DICOM tags |

### Impact

- Future correctness risk if physical-unit features assume MPP is always present.

### Code Location

- `src/giant/wsi/types.py:45-46` - Nullable MPP definition
- Future specs that will use MPP for measurements

### Mitigation

When physical measurements are implemented, add a helper method to WSIMetadata (or a dedicated measurement service) to centralize the guard:

```python
def get_mpp(self) -> tuple[float, float]:
    """Get MPP values, raising if uncalibrated."""
    if self.mpp_x is None or self.mpp_y is None:
        raise ValueError(
            f"Slide {self.path} has no MPP calibration data. "
            "Physical measurements are not available."
        )
    return (self.mpp_x, self.mpp_y)

def has_calibration(self) -> bool:
    """Check if slide has MPP calibration data."""
    return self.mpp_x is not None and self.mpp_y is not None
```
