# BUG-010: MPP (Microns Per Pixel) Is Nullable With No Guards

## Severity: P2 (Medium Priority) - Time Bomb

## Status: Open

## Description

`WSIMetadata.mpp_x` and `mpp_y` are `float | None` to handle slides without calibration data. However, there are NO guards in the codebase to check for `None` before using these values. Any future code that uses MPP for physical distance calculations will crash.

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

The current codebase doesn't use MPP for calculations, so this is dormant. But it's a guaranteed crash when:
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

- Silent None propagation until crash
- Crashes on uncalibrated slides
- No clear error message about missing calibration

### Code Location

- `src/giant/wsi/types.py:45-46` - Nullable MPP definition
- Future specs that will use MPP for measurements

### Mitigation

Add a helper method to WSIMetadata:

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
