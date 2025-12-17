# Bug Tracking - GIANT WSI Pipeline

## Summary

This directory tracks bugs discovered during the Spec-05.5 Integration Checkpoint deep audit.

The unit test suite is **not** “bogus”: mocking OpenSlide is an intentional unit-testing strategy to keep tests fast, deterministic, and free of large binary WSI files. Integration tests now exist to exercise the real OpenSlide stack against a real WSI file, and are **skipped by default** unless a test slide is provided.

## Bug Index

### P0 - Critical (Blocks Spec-06)

| ID | Title | Status |
|----|-------|--------|
| [BUG-004](./BUG-004-missing-integration-tests.md) | No Integration Tests with Real WSI Files | **Fixed (pending merge)** |

### P1 - High Priority (Could Crash / OOM)

| ID | Title | Status |
|----|-------|--------|
| [BUG-003](./BUG-003-huge-region-no-protection.md) | Huge Region Requests Can OOM | **Fixed (pending merge)** |

### P2 - Medium Priority (Correctness / Spec-05.5 Doc Gaps)

| ID | Title | Status |
|----|-------|--------|
| [BUG-005](./BUG-005-single-level-slide-untested.md) | Single-Level Slide Behavior Untested | Open |
| [BUG-002](./BUG-002-spec-contradiction-upsample-small-regions.md) | Spec-05.5 Contradicts Spec-05 on Upsampling | **Fixed (pending merge)** |

### P3 - Low Priority (DevEx / Future-Proofing)

| ID | Title | Status |
|----|-------|--------|
| [BUG-001](./BUG-001-boundary-crop-no-handling.md) | Boundary Behavior Not Explicitly Specified (Pad vs Clamp) | Open (Policy) |
| [BUG-007](./BUG-007-entire-test-suite-mocked.md) | Prior “bogus tests” claim was inaccurate (see doc) | Closed (Doc corrected) |
| [BUG-008](./BUG-008-api-keys-silent-none.md) | Missing “required key” guardrails at use sites | Open (Spec-06/CLI) |
| [BUG-009](./BUG-009-font-loading-silent-fallback.md) | Font Loading Falls Back Silently | Open (DevEx) |
| [BUG-010](./BUG-010-mpp-nullable-no-guards.md) | Optional MPP Needs Helper/Guards When Used | Open (Future) |
| [BUG-011](./BUG-011-unused-geometry-validator.md) | GeometryValidator Is Staged for Spec-09 (Not Dead) | Open (Deferred) |
| [BUG-012](./BUG-012-download-silent-auth.md) | HF Download Auth Behavior Not Surfaced | Open (DevEx) |

## Key Findings

### 1. Real OpenSlide integration coverage exists (BUG-004)

- `tests/integration/wsi/` contains opt-in integration tests that exercise the real OpenSlide stack.
- By default these tests are skipped unless `WSI_TEST_FILE` points to a real slide (or a small local test slide exists under `tests/integration/wsi/data/`).
- Recommendation: run these tests at least once locally before starting Spec-06, and optionally wire them into CI using a small public test slide.

### 2. Unit tests are valuable (not “100% mocked”)

- Many tests exercise real behavior (level selection math, geometry primitives/transforms/validation, PIL resizing + JPEG/Base64 encoding).
- Mocking OpenSlide in unit tests is appropriate; integration tests should cover the real stack (BUG-004).

### 3. Largest real runtime risk is memory blowups (BUG-003)

- `openslide.read_region` allocates an RGBA buffer of `w*h` pixels; extremely large region requests can OOM.
- Mitigation implemented: `CropEngine.crop()` enforces a configurable maximum read dimension to prevent extreme allocations; future work can refine this to a pixel-budget-based limit or thumbnail fallback policy.

## Severity Definitions

- **P0 (Critical)**: Blocks progress. Must fix before Spec-06.
- **P1 (High)**: Will cause production bugs. Should fix before Spec-06.
- **P2 (Medium)**: Edge cases. Can document and address later.
- **P3 (Low)**: Nice to have. Future optimization.

## Resolution Priority

### MUST FIX Before Spec-06

1. **BUG-004**: Add opt-in integration tests with a real WSI file (**done**; run once locally)
2. **BUG-003**: Add huge-region protection / pixel budget (**done**; dimension guard)

### SHOULD FIX Before Spec-06

3. **BUG-002**: Update Spec-05.5 P1-3 to match paper/spec-05 (no upsample) (**done**)

### CAN DEFER

- **BUG-001, BUG-005, BUG-008, BUG-009, BUG-010, BUG-011, BUG-012**: Non-blocking (policy/DevEx/future-proofing)

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
