# BUG-007: “Entire Test Suite Is Mocked” Claim Was Inaccurate

## Severity: P3 (Low Priority) - Documentation Correction

## Status: Closed (Superseded by BUG-004)

## Description

This document corrects an overstated claim from the Spec-05.5 checkpoint.

What is **true**:
- We have opt-in integration tests, but CI typically does **not** exercise the real OpenSlide stack unless a real test slide is provided (tracked as **BUG-004**).

What is **not true**:
- The test suite is not “100% mocked”.
- The test suite does not “only test mock interactions”.
- Several tests exercise real behavior (math, validation, image resizing/encoding).

## Why mocking is appropriate here (unit tests)

- Whole-slide images are large binaries (10MB–GB); committing them to the repo is undesirable.
- OpenSlide behavior depends on OS + native libs; unit tests should be deterministic and fast.
- Mocking OpenSlide allows us to test **our** responsibilities:
  - Parameter validation
  - Error wrapping (`WSIOpenError` / `WSIReadError`)
  - Correct coordinate conventions (Level-0 location, level-space size)
  - RGBA → RGB conversion
  - Crop resize math + Base64 encoding

Integration tests should cover the real stack (BUG-004), not replace unit tests.

## Examples of non-mocked “real behavior” tests

- `tests/unit/core/test_level_selector.py`: tests level-selection math directly.
- `tests/unit/geometry/test_primitives.py`: tests Pydantic validation behavior.
- `tests/unit/geometry/test_transforms.py`: tests coordinate transform math.
- `tests/unit/geometry/test_validators.py`: tests bounds validation/clamping behavior.
- `tests/unit/core/test_crop_engine.py`: exercises PIL resizing and verifies Base64 decodes to a JPEG image.
