# BUG-004: No Integration Tests with Real WSI Files

## Severity: P0 (Critical)

## Status: Fixed (PR pending)

## Description

The codebase has **no integration tests** with real WSI files committed yet. This means:

1. OpenSlide integration is untested in CI
2. Vendor-specific behaviors are unknown
3. Edge cases at slide boundaries are untested
4. Memory behavior with real data is untested

### Related Spec Tests

All P0 tests require real SVS files:

- **P0-1**: Open real SVS file
- **P0-2**: Thumbnail generation
- **P0-3**: Read region at L0
- **P0-4**: Read region at max level
- **P0-5**: Coordinate roundtrip
- **P0-6**: Level selection for target
- **P0-7**: Crop pipeline end-to-end

### Current State

```text
tests/
├── unit/           # Extensive unit tests (mocks used where appropriate)
└── integration/
    └── wsi/        # Directory exists, but currently contains no tests
```

### Expected State (from Spec-05.5)

```text
tests/
├── unit/           # Mocked unit tests
└── integration/
    └── wsi/
        ├── conftest.py          # Fixtures for test slides
        ├── test_wsi_reader.py   # P0-1 through P0-4
        ├── test_coordinates.py  # P0-5
        ├── test_level_selector.py # P0-6
        └── test_crop_pipeline.py  # P0-7
```

### Test Data Requirements

Minimum: ONE real `.svs` file for CI.

**Option 1: OpenSlide Test Data (Recommended for CI)**

```bash
# Small (~10MB) synthetic Aperio file
curl -LO https://openslide.cs.cmu.edu/download/openslide-testdata/Aperio/CMU-1-Small-Region.svs
```

**Option 2: Skip Integration in CI**

Mark integration tests with `@pytest.mark.integration` and skip in CI unless test data is available.

### Proposed Fix

1. Add tests under the existing `tests/integration/wsi/` directory
2. Add `conftest.py` with fixtures that:
   - Check for `WSI_TEST_FILE` env var
   - Skip tests if no test file available
   - Download small test file if configured
3. Implement P0 tests using real `WSIReader`
4. Add `@pytest.mark.integration` marker
5. Add CI step to run integration tests (optional)

### Impact

- **Production bugs** will only be discovered in real usage
- **Vendor compatibility** issues are invisible
- **Memory leaks** or resource handling bugs are undetected
- **Spec-05.5 sign-off criteria** cannot be met

### Sign-Off Criteria (from Spec-05.5)

> - All P0 tests pass
> - At least ONE real `.svs` file tested end-to-end
> - Integration test file committed to `tests/integration/wsi/`
