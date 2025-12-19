# BUG-015: Visualizer Missing Images / Overlays (Spec-12 Drift)

## Severity: P3 (Low Priority) - UX / Debuggability

## Status: Open

## Description

`giant visualize` generates an HTML report, but it does **not** display:

- The WSI thumbnail (with axis guides)
- The crop images from each step (`turn.image_base64`)
- Any overlay/highlight of the cropped region on the thumbnail

Spec-12’s “Visualization” design section describes these as core features for an “interactive HTML trajectory visualization”.

Today the visualizer is effectively a **text-only** timeline (reasoning + region numbers), which significantly reduces its value for debugging navigation correctness (coordinate mistakes, off-by-one crops, wrong tissue, etc.).

## Evidence (Current Behavior)

- `src/giant/cli/visualizer.py`:
  - Does not render any `<img>` tags
  - Does not read `turn["image_base64"]` for display (it only parses `region` and `reasoning`)

## Expected Behavior

The visualization should, at minimum:

1. Render the initial thumbnail image (axis-guided).
2. Render each crop image per step.
3. Show the crop region coordinates (already present).

Optionally (but spec-aligned):

- Draw the crop region on the thumbnail (SVG/canvas overlay).
- Provide navigation controls (carousel/stepper) and collapsible sections.

## Impact

- Harder to validate agent correctness visually.
- Easy to miss geometry/coordinate bugs (the report lacks the actual evidence).
- Limits usefulness of saved trajectories for senior review/debugging.

## Proposed Fix

1. Embed images as data URLs:
   - Thumbnail: `data:image/jpeg;base64,<...>`
   - Crop images: `data:image/jpeg;base64,<...>`
2. Add a size-aware strategy to avoid generating enormous HTML:
   - Option A: Write images as separate `.jpg` files to an output directory and reference them.
   - Option B: Allow `--inline-images/--no-inline-images` in the CLI.
3. Add overlay rendering:
   - Use an SVG overlay positioned over the thumbnail to draw the crop rectangle.

## Testing Required

- Unit test: HTML includes `<img>` tags when `image_base64` is present.
- Unit test: Crop images and thumbnail are wired correctly per step.
- Regression test: Existing “minimal” trajectory shapes still render without exceptions.
