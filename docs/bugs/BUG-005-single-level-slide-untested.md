# BUG-005: Single-Level Slide Behavior Untested with Real Files

## Severity: P2 (Medium Priority)

## Status: Open - Needs Integration Test

## Description

The `PyramidLevelSelector` handles single-level slides correctly in unit tests (mocked), but this has never been validated with a real single-level TIFF file.

### Related Spec Tests

- **P2-1**: Single-level slide - "Open slide with `level_count=1` - No index errors, level 0 used"

### Current Unit Test Coverage

`tests/unit/core/test_level_selector.py::test_single_level_always_returns_level0` - PASSES (mocked)

```python
def test_single_level_always_returns_level0():
    metadata = WSIMetadata(
        level_count=1,
        level_dimensions=((100000, 80000),),
        level_downsamples=(1.0,),
        # ...
    )
    # Test passes with mock
```

### Untested Scenarios

1. Real single-level TIFF/SVS file
2. OpenSlide metadata parsing for single-level
3. `level_dimensions` tuple with single element
4. Actual image read at level 0

### Code Location

- `src/giant/core/level_selector.py:166-181` - `_find_closest_level()`
- `src/giant/wsi/reader.py:126-136` - Metadata extraction

### Testing Required

- Create or obtain single-level test TIFF
- Integration test: Open, read metadata, verify `level_count=1`
- Integration test: Crop region, verify level 0 used
