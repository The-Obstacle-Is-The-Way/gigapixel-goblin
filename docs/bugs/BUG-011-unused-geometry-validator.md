# BUG-011: GeometryValidator Exists But Is Never Used

## Severity: P1 (High Priority) - Dead Code

## Status: Open

## Description

The codebase has a fully implemented `GeometryValidator` class with `validate()` and `clamp_region()` methods, but **it is never used anywhere in the production code**. The crop pipeline passes unvalidated regions directly to OpenSlide.

### The Unused Code

```python
# src/giant/geometry/validators.py - 155 lines of dead code
class GeometryValidator:
    def validate(self, region: Region, bounds: Size, *, strict: bool = True) -> bool:
        """Validate that a region is within bounds."""
        # FULLY IMPLEMENTED, NEVER CALLED

    def clamp_region(self, region: Region, bounds: Size) -> Region:
        """Clamp a region to valid bounds."""
        # FULLY IMPLEMENTED, NEVER CALLED
```

### Where It Should Be Used

```python
# src/giant/core/crop_engine.py:102-165
def crop(self, region: Region, ...) -> CroppedImage:
    # NO VALIDATION HERE!
    metadata = self._reader.get_metadata()
    # region could be outside slide bounds - no check!

    # SHOULD BE:
    # bounds = Size(width=metadata.width, height=metadata.height)
    # validator = GeometryValidator()
    # if not validator.is_within_bounds(region, bounds):
    #     region = validator.clamp_region(region, bounds)
```

### Evidence

```bash
# Search for GeometryValidator usage in production code
grep -r "GeometryValidator" src/
# Only found in: src/giant/geometry/__init__.py (export)
#                src/giant/geometry/validators.py (definition)
# NOT found in: src/giant/core/crop_engine.py
```

### Why This Is Bad

1. **Code exists, tests exist, but nothing uses it**
2. **Boundary bugs**: Invalid regions passed to OpenSlide
3. **Wasted effort**: 155 lines of code + 268 lines of tests = 0 value
4. **Documentation lie**: The docstring says "should only be used when explicitly chosen by the agent's error-recovery policy (Spec-09)" but Spec-09 doesn't exist yet

### The Disconnect

| Component | Status |
|-----------|--------|
| `GeometryValidator` class | ✓ Implemented |
| `GeometryValidator` tests | ✓ 26 tests pass |
| `CropEngine` uses validator | ✗ Never integrated |
| Agent error recovery (Spec-09) | ✗ Not implemented |

### Impact

- Invalid regions crash or behave unexpectedly
- Useful code sits unused
- Tests verify dead code

### Code Location

- `src/giant/geometry/validators.py` - Dead code
- `src/giant/core/crop_engine.py` - Missing integration
- `tests/unit/geometry/test_validators.py` - Tests for dead code

### Fix Required

Either:
1. **Integrate now**: Add validation/clamping to `CropEngine.crop()`
2. **Remove dead code**: Delete validators.py until Spec-09
3. **Mark as future**: Add `# TODO(spec-09): Integrate with error recovery`
