# BUG-019: Axis Guide Font Fallback Can Degrade Label Legibility

## Severity: P3 (Robustness / Reproducibility)

## Status: Closed (Fixed)

## Description
Axis guide labels are rendered via `PIL.ImageFont.truetype`. If neither `DejaVuSans.ttf` nor `Arial.ttf` is available, `AxisGuideGenerator._get_font()` logs a warning and falls back to `ImageFont.load_default()`.

This fallback is **not silent** (it warns), but it can still materially degrade navigation because PIL’s default bitmap font is often small/pixelated and ignores the configured `font_size`.

## Why This Matters
- **Model performance risk:** If coordinates are hard to read on the thumbnail, the VLM may choose poor crops or fail to comply with coordinate constraints.
- **Environment sensitivity:** Minimal Docker images frequently lack TrueType fonts; behavior can vary across machines/CI.

## Evidence
- `src/giant/geometry/overlay.py`: `_get_font()` tries DejaVuSans/Arial, then warns + returns `ImageFont.load_default()`.
- Historical context: `docs/bugs/archive/BUG-009-font-loading-silent-fallback.md` fixed the “no warning” issue; this bug is about the remaining **quality/reproducibility** gap.

## Resolution
- Added `OverlayStyle.strict_font_check` + `AxisGuideGenerator._get_font()` now raises when enabled and no TrueType font is available.
- Wired through `AgentConfig.strict_font_check` and CLI flags: `giant run --strict-font-check` / `giant benchmark --strict-font-check`.
- Added unit coverage: `tests/unit/geometry/test_overlay.py` asserts strict mode raises when fonts are unavailable.

## Follow-ups (Optional)
- Bundle a small OSS TTF in-package and prefer it before system fonts to reduce environment variance further.
