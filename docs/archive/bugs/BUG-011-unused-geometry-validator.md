# BUG-011: GeometryValidator Exists But Is Never Used

## Severity: P3 (Low Priority) - Staged for Spec-09

## Status: RESOLVED (Archived 2025-12-19)

## Resolution

**Fixed in Spec-09 implementation.** The `GeometryValidator` is now fully integrated into `GIANTAgent.run()`:

- Imported at `src/giant/agent/runner.py:33`
- Used for strict validation at lines 325-329:

  ```python
  try:
      self._validator.validate(region, self._slide_bounds, strict=True)
  except ValidationError as e:
      logger.warning("Invalid crop region: %s", e)
      return await self._handle_invalid_region(action, messages, str(e))
  ```

This follows Spec-09's design: "strict by default; clamp only as an explicit, test-covered recovery path."

---

## Original Description (Historical)

`GeometryValidator` is currently unused in production code, but this is intentional: Spec-09 explicitly places bbox validation in the agent loop ("strict by default; clamp only as an explicit, test-covered recovery path"). Until Spec-09 is implemented, `GeometryValidator` is a staged utility.

### The Unused Code

```python
# src/giant/geometry/validators.py - staged utility (used by Spec-09)
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

This is scaffolding for Spec-09. The tests are still valuable because:
1. They lock down bounds semantics before the LLM loop arrives.
2. They provide a known-correct component for error recovery once the agent is built.

### The Disconnect (Expected Until Spec-09)

| Component | Status |
|-----------|--------|
| `GeometryValidator` class | ✓ Implemented |
| `GeometryValidator` tests | ✓ 26 tests pass |
| `CropEngine` uses validator | ✗ Never integrated |
| Agent error recovery (Spec-09) | ✗ Not implemented (yet) |

### Impact

- Until Spec-09 is implemented, invalid bbox handling lives in OpenSlide’s padding behavior (out-of-bounds pixels → transparent → black after RGB conversion).
- Once Spec-09 lands, `GeometryValidator` becomes the single source of truth for bounds validation and recovery policy.

### Code Location

- `src/giant/geometry/validators.py` - Staged validation/clamping utility
- `docs/specs/spec-09-giant-agent.md` - Defines how it’s used (strict by default)
- `tests/unit/geometry/test_validators.py` - Unit tests for bounds semantics

### Fix Required

Either:
1. **Leave as-is** (recommended): integrate in Spec-09 as designed.
2. **Document the staging**: keep this as a known “will be used by Spec-09” utility.
