# BUG-009: Font Loading Has Silent Fallback - No Warning

## Severity: P3 (Low Priority) - DevEx

## Status: Open

## Description

The `AxisGuideGenerator._get_font()` method silently falls back to PIL's default bitmap font when TrueType fonts aren't available. No warning is logged, so users don't know their overlay text might look terrible.

### Current Code

```python
# src/giant/geometry/overlay.py:173-188
def _get_font(self) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Get font for labels, with fallback to default."""
    try:
        return ImageFont.truetype("DejaVuSans.ttf", self.style.font_size)
    except OSError:
        try:
            return ImageFont.truetype("Arial.ttf", self.style.font_size)
        except OSError:
            # SILENT FALLBACK - NO WARNING!
            return ImageFont.load_default()
```

### Problem

1. **No logging**: User doesn't know fonts failed to load
2. **Quality degradation**: PIL's default font is low-resolution bitmap
3. **font_size ignored**: `ImageFont.load_default()` ignores the configured `font_size`
4. **Silent degradation**: Overlays look bad with no indication why

### Expected Behavior

```python
def _get_font(self) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Get font for labels, with fallback to default."""
    try:
        return ImageFont.truetype("DejaVuSans.ttf", self.style.font_size)
    except OSError:
        try:
            return ImageFont.truetype("Arial.ttf", self.style.font_size)
        except OSError:
            logger.warning(
                "No TrueType fonts available (DejaVuSans.ttf, Arial.ttf). "
                "Using low-resolution default font. Install fonts for better quality."
            )
            return ImageFont.load_default()
```

### Impact

- Cosmetic/DevEx: overlay labels may look pixelated with no indication why.

### Code Location

- `src/giant/geometry/overlay.py:173-188` - `_get_font()` method

### Testing Required

- Unit test: Verify warning logged when falling back to default font
- Manual test: Check overlay quality with/without TrueType fonts
