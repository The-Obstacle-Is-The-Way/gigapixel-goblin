# BUG-023: Axis Guide Labels Use “K” Abbreviation (Not Absolute Coordinates)

## Severity: P2 (Paper/spec mismatch impacting navigation)

## Status: Closed (Fixed)

## Description
The paper specifies that the thumbnail’s axis guides are “labeled with **absolute level-0 pixel coordinates**.” Specs mirror this expectation (examples like `10000`, `20000`, `15000`).

The implementation previously formatted larger coordinates using “K” notation (e.g., `15000 → "15K"`), controlled by hard-coded thresholds:

```python
_COORD_THRESHOLD_LARGE = 10000  # 15000 -> "15K"
_COORD_THRESHOLD_MEDIUM = 1000  # 1500  -> "1.5K"
```

`OverlayStyle.num_guides=4` is **correct** and paper-faithful; the issue is specifically the **label formatting** (and, secondarily, the hard-coded formatting thresholds).

## Why This Matters
- **Prompt/visual mismatch:** The system prompt and specs describe absolute coordinates (e.g., `10000`), but the image shows abbreviated labels (e.g., `10K`).
- **Navigation accuracy:** Abbreviations increase the risk the model outputs non-numeric coordinates (“10K”) or makes off-by-thousands errors.
- **Reproducibility:** Small presentation differences can materially change LMM behavior.

## Evidence
- Paper: `_literature/markdown/giant/giant.md` states labels are absolute level-0 pixel coordinates.
- Spec: `docs/specs/spec-03-coordinates.md` describes rendering labels like `"15000"`.
- Historical code: `src/giant/geometry/overlay.py` formatted coordinates with “K” abbreviations.

## Resolution
- Removed “K” abbreviations; axis labels now render as absolute integers (paper/spec-faithful).
- Added unit coverage in `tests/unit/geometry/test_overlay.py` to prevent regressions.

## Follow-ups (Optional)
- If compact labels are desired for human debugging, make the behavior explicit and configurable (defaulting to paper-faithful absolute integers).
