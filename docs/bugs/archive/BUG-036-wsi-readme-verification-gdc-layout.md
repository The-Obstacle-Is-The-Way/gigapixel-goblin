# BUG-036: `data/wsi/README.md` Verification Assumes Flat TCGA Layout

## Severity: P1 (Docs cause false "missing data" signals)

## Status: ✅ Fixed (2025-12-26)

## Summary

`data/wsi/README.md` includes a verification loop that checks for files at `data/wsi/tcga/<filename>.svs`. This fails when TCGA slides are downloaded using `gdc-client`, which typically stores files under `data/wsi/tcga/<file_id>/<uuid-suffixed filename>.svs` (the recommended layout in `docs/DATA_ACQUISITION.md` and supported by `WSIPathResolver`).

## Repro

1. Download TCGA slides using `gdc-client download -d data/wsi/tcga/` (default layout).
2. Run the “Check against file lists” loop in `data/wsi/README.md`.
3. It reports many missing files even though `giant check-data tcga` can resolve them.

## Root Cause

- Documentation drift: the README uses a flat-path check, but the codebase supports and recommends the per-`file_id` directory structure.

## Proposed Fix

1. **Prefer resolver-based verification**
   - Update `data/wsi/README.md` to recommend:
     - `uv run giant check-data tcga`
     - `uv run giant check-data tcga_expert_vqa`
     - `uv run giant check-data tcga_slidebench`

2. **If keeping a shell-based loop**
   - Either remove the flat `-f tcga/$f` loop, or rewrite it to:
     - Check for `tcga/<file_id>/*.svs` when `file_id` is available, or
     - Use a stem glob (e.g., `TCGA-...-DX1.*.svs`) across subdirectories.

3. **Housekeeping**
   - Update any “Spec-12 will add a stable CLI” language (CLI already exists).

## Acceptance Criteria

- Following `data/wsi/README.md` produces correct validation results for both:
  - Flat layout (`tcga/<filename>.svs`), and
  - `gdc-client` layout (`tcga/<file_id>/<uuid-suffixed filename>.svs`).
