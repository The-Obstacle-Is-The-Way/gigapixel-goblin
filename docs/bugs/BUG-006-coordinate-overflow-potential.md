# BUG-006: Potential Coordinate Overflow for Very High Resolution Slides

## Severity: P2 (Medium Priority)

## Status: Open - Needs Analysis

## Description

The codebase uses Python `int` for coordinates, which prevents overflow in Python. However, when interfacing with OpenSlide (C library), there may be edge cases with very high resolution slides (>100,000 pixels).

### Related Spec Tests

- **P2-4**: Very high resolution - "Slide with dimensions > 100,000 px - Coordinate math doesn't overflow"

### Analysis

**Python Side (Safe):**

```python
# Python integers have arbitrary precision - no overflow
coord = 150000 * 4  # 600000, no overflow
```

**OpenSlide/C Side (Potential Issue):**

OpenSlide uses C types internally. For most operations, 32-bit signed integers are used:

- Max value: 2,147,483,647
- A 100,000 x 100,000 slide at Level-0 is fine
- Edge case: 200,000 x 200,000 slide (rare but exists in research)

### Current Code

```python
# In wsi/types.py
def level0_to_level(coord: tuple[int, int], downsample: float) -> tuple[int, int]:
    x, y = coord
    return (int(x / downsample), int(y / downsample))  # int() truncates, no overflow
```

### Real-World Slide Dimensions

| Vendor | Typical Max | Notes |
|--------|-------------|-------|
| Aperio | 100,000 x 60,000 | Common |
| Hamamatsu | 150,000 x 100,000 | Nanozoomer |
| Leica | 120,000 x 80,000 | Versa |

Most slides are well under 200,000 in any dimension.

### Recommendation

**Low risk** - Python's arbitrary precision integers prevent overflow on our side. OpenSlide handles large coordinates internally. Add defensive logging:

```python
def read_region(self, location, level, size):
    if location[0] > 2_000_000_000 or location[1] > 2_000_000_000:
        logger.warning(f"Very large coordinates: {location} - potential OpenSlide issues")
    # ... existing code
```

### Testing Required

- Unit test with coordinates near INT32_MAX (mocked)
- Integration test with largest available test slide
- Document known slide dimension limits
