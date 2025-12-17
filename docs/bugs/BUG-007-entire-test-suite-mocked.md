# BUG-007: Entire Test Suite Is Mocked - Zero Real Behavior Tests

## Severity: P0 (Critical) - TESTS ARE BOGUS

## Status: Open

## Description

**The entire test suite (287 tests) only tests mock interactions, NOT real behavior.** This is extremely dangerous because:

1. Tests pass when mocks are called correctly, even if the real implementation is broken
2. The comment in `test_reader.py:4` says "Integration tests with real files are in tests/integration/" but **that directory does not exist**
3. We have 99% code coverage but ZERO confidence the code works

### Evidence

**test_reader.py:220-231 - Tests Mock Calls, Not Behavior:**
```python
def test_read_region_basic(
    self, reader_with_mock: tuple[WSIReader, MagicMock]
) -> None:
    """Test basic read_region call."""
    reader, mock = reader_with_mock

    result = reader.read_region((1000, 2000), level=0, size=(512, 512))

    # THIS ONLY TESTS THAT THE MOCK WAS CALLED
    # IT DOES NOT TEST THAT OPENSLIDE ACTUALLY WORKS
    mock.read_region.assert_called_once_with((1000, 2000), 0, (512, 512))
```

**test_crop_engine.py:250-262 - Tests Mock Output, Not Real Resize:**
```python
def test_crop_resizes_image_to_target_size(
    self,
    crop_engine: CropEngine,
) -> None:
    """Test crop() resizes image so long side equals target_size."""
    region = Region(x=0, y=0, width=10000, height=8000)

    result = crop_engine.crop(region, target_size=1000)

    # The mock returns a pre-sized image
    # This tests the mock setup, NOT the actual PIL resize behavior
    assert max(result.image.width, result.image.height) == 1000
```

### What The Tests Actually Test

| Test File | What It Claims To Test | What It Actually Tests |
|-----------|----------------------|----------------------|
| test_reader.py | WSIReader with OpenSlide | Mock was called correctly |
| test_crop_engine.py | Image cropping pipeline | Mock interactions |
| test_level_selector.py | Level selection algorithm | **ACTUALLY TESTS REAL BEHAVIOR** ✓ |
| test_primitives.py | Pydantic models | **ACTUALLY TESTS REAL BEHAVIOR** ✓ |
| test_transforms.py | Coordinate transforms | **ACTUALLY TESTS REAL BEHAVIOR** ✓ |
| test_validators.py | Geometry validation | **ACTUALLY TESTS REAL BEHAVIOR** ✓ |

### The Good Tests vs The Bad Tests

**GOOD TESTS (test real behavior, no mocks needed):**
- `test_level_selector.py` - Tests actual math with WSIMetadata instances
- `test_primitives.py` - Tests actual Pydantic validation
- `test_transforms.py` - Tests actual coordinate math
- `test_validators.py` - Tests actual geometry validation

**BAD TESTS (only test mock interactions):**
- `test_reader.py` - 100% mocked, tests nothing real
- `test_crop_engine.py` - 100% mocked, tests nothing real

### Impact

- **False confidence**: 287 passing tests mean nothing
- **Hidden bugs**: Real OpenSlide integration issues are invisible
- **Production failures**: First real WSI file will likely reveal bugs

### Root Cause

The comment says "Integration tests with real files are in tests/integration/" but someone forgot to actually create them. The unit tests became the only tests, and they only test mocks.

### Fix Required

1. Create `tests/integration/wsi/` directory
2. Download real test WSI file (CMU-1-Small-Region.svs is 10MB)
3. Write REAL tests that:
   - Open actual SVS files
   - Read actual regions
   - Verify actual image content
   - Test actual resize behavior
4. Mark mock-based tests as what they are: "unit tests for interface contracts"

### Code Location

- `tests/unit/wsi/test_reader.py` - 100% mocked
- `tests/unit/core/test_crop_engine.py` - 100% mocked
