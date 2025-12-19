# BUG-023: Axis Guide Labels Use “K” Abbreviation (Not Absolute Coordinates)

## Severity: P2 (Paper/spec mismatch impacting navigation)

## Status: Open

## Description
The paper specifies that the thumbnail’s axis guides are “labeled with **absolute level-0 pixel coordinates**.” Specs mirror this expectation (examples like `10000`, `20000`, `15000`).

The current implementation formats larger coordinates using “K” notation (e.g., `15000 → "15K"`), controlled by hard-coded thresholds:

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
- Code: `src/giant/geometry/overlay.py` uses `_format_coordinate()` to emit “K” abbreviations.

## Proposed Fix
1. Render **full integer coordinates** on axis guide labels (no abbreviations) to match the paper/spec text.
2. If compact formatting is desired, make it explicit and configurable (e.g., an `OverlayStyle.label_format` enum, or dual labels like `15000 (15K)`).
3. Move formatting thresholds into `OverlayStyle` only if abbreviations remain supported.
