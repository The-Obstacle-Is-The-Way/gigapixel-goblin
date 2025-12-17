# Bug Tracking - GIANT WSI Pipeline

## Summary

This directory tracks bugs discovered during the Spec-05.5 Integration Checkpoint deep audit.

**CRITICAL FINDING: The test suite is fundamentally broken.** 287 tests pass but only verify mock interactions, not real behavior. Zero integration tests exist.

## Bug Index

### P0 - Critical (Blocks Progress)

| ID | Title | Status |
|----|-------|--------|
| [BUG-004](./BUG-004-missing-integration-tests.md) | No Integration Tests with Real WSI Files | Open |
| [BUG-007](./BUG-007-entire-test-suite-mocked.md) | **Entire Test Suite Is Mocked - Zero Real Behavior Tests** | Open |

### P1 - High Priority (Will Cause Production Bugs)

| ID | Title | Status |
|----|-------|--------|
| [BUG-001](./BUG-001-boundary-crop-no-handling.md) | Boundary Crop Has No Graceful Handling | Open |
| [BUG-002](./BUG-002-spec-contradiction-upsample-small-regions.md) | Spec Contradiction - Small Region Upsampling | Open (Design Decision) |
| [BUG-003](./BUG-003-huge-region-no-protection.md) | Huge Region Has No Memory Protection | Open |
| [BUG-008](./BUG-008-api-keys-silent-none.md) | API Keys Are Silently None - No Validation | Open |
| [BUG-011](./BUG-011-unused-geometry-validator.md) | GeometryValidator Exists But Is Never Used | Open |

### P2 - Medium Priority (Edge Cases)

| ID | Title | Status |
|----|-------|--------|
| [BUG-005](./BUG-005-single-level-slide-untested.md) | Single-Level Slide Behavior Untested | Open |
| [BUG-006](./BUG-006-coordinate-overflow-potential.md) | Potential Coordinate Overflow | Open |
| [BUG-009](./BUG-009-font-loading-silent-fallback.md) | Font Loading Has Silent Fallback - No Warning | Open |
| [BUG-010](./BUG-010-mpp-nullable-no-guards.md) | MPP (Microns Per Pixel) Is Nullable With No Guards | Open |
| [BUG-012](./BUG-012-download-silent-auth.md) | HuggingFace Download Silently Uses No Auth | Open |

## Key Findings

### 1. Tests Are Bogus (BUG-007)

```
287 tests pass, but ZERO test real behavior.

test_reader.py: 100% mocked - only tests mock.assert_called()
test_crop_engine.py: 100% mocked - only tests mock.assert_called()

The comment says "Integration tests in tests/integration/"
but that directory DOES NOT EXIST.
```

### 2. Dead Code (BUG-011)

```
GeometryValidator: 155 lines of production code
test_validators.py: 268 lines of tests

Usage in production code: ZERO
```

### 3. Silent Failures

| Location | Issue |
|----------|-------|
| `config.py` | API keys silently None |
| `download.py` | HF token silently None |
| `overlay.py` | Font fallback silent |
| `crop_engine.py` | No bounds validation |

### 4. Time Bombs

| Issue | Trigger |
|-------|---------|
| MPP is nullable | Physical measurement code added |
| No bounds check | LLM requests edge region |
| No memory guard | LLM requests full slide |

## Severity Definitions

- **P0 (Critical)**: Blocks progress. Must fix before Spec-06.
- **P1 (High)**: Will cause production bugs. Should fix before Spec-06.
- **P2 (Medium)**: Edge cases. Can document and address later.
- **P3 (Low)**: Nice to have. Future optimization.

## Resolution Priority

### MUST FIX Before Spec-06

1. **BUG-007**: Acknowledge test suite limitations, add real integration tests
2. **BUG-004**: Set up integration test infrastructure
3. **BUG-001**: Add boundary crop handling (integrate existing `clamp_region`)
4. **BUG-011**: Either integrate GeometryValidator or document why unused

### SHOULD FIX Before Spec-06

5. **BUG-003**: Add huge region protection
6. **BUG-008**: Add API key validation with clear errors
7. **BUG-002**: Make design decision on upsampling, update spec

### CAN DEFER

- **BUG-005, BUG-006**: Document as known limitations
- **BUG-009, BUG-010, BUG-012**: Low risk, add logging

## Audit Methodology

1. Read ALL source files (`src/giant/**/*.py`)
2. Read ALL test files (`tests/**/*.py`)
3. Check for:
   - Halfway implementations
   - Silent fallbacks / degradation
   - Things that should fail loudly
   - Over-mocking in tests
   - Nullable handling without guards
   - Dead code / unused utilities

## Discovered During

- **Spec-05.5 Integration Checkpoint Review**
- **Date**: 2025-12-17
- **Reviewer**: AI Code Review (Claude)

## Files Examined

### Source (20 files)
- `src/giant/__init__.py`
- `src/giant/config.py`
- `src/giant/cli/main.py`
- `src/giant/data/download.py`
- `src/giant/utils/logging.py`
- `src/giant/geometry/primitives.py`
- `src/giant/geometry/transforms.py`
- `src/giant/geometry/validators.py`
- `src/giant/geometry/overlay.py`
- `src/giant/wsi/reader.py`
- `src/giant/wsi/types.py`
- `src/giant/wsi/exceptions.py`
- `src/giant/core/level_selector.py`
- `src/giant/core/crop_engine.py`
- (+ init files)

### Tests (19 files)
- `tests/unit/wsi/test_reader.py`
- `tests/unit/wsi/test_types.py`
- `tests/unit/wsi/test_exceptions.py`
- `tests/unit/core/test_level_selector.py`
- `tests/unit/core/test_crop_engine.py`
- `tests/unit/geometry/test_primitives.py`
- `tests/unit/geometry/test_transforms.py`
- `tests/unit/geometry/test_validators.py`
- `tests/unit/geometry/test_overlay.py`
- `tests/unit/test_config.py`
- `tests/unit/test_cli.py`
- `tests/unit/test_download.py`
- `tests/unit/test_logging.py`
- (+ init files)
