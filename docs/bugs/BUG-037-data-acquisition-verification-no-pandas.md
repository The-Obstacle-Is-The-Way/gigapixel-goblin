# BUG-037: `docs/DATA_ACQUISITION.md` Verification Requires `pandas` (Not Installed)

## Severity: P2 (Docs friction / onboarding failure)

## Status: Proposed Fix Spec (Not Implemented)

## Summary

`docs/DATA_ACQUISITION.md` includes a verification snippet that imports `pandas`, but `pandas` is not listed in `pyproject.toml` dependencies. On a fresh setup (`uv sync`), the snippet fails and blocks users from validating their WSI downloads.

## Repro

```bash
uv sync
python -c "import pandas as pd"
```

## Root Cause

- Doc snippet was written assuming a data-science stack, but this repo intentionally avoids `pandas` as a hard dependency.
- The repo already provides a CLI-native verifier (`giant check-data`) that doesn’t require extra packages.

## Proposed Fix

1. Replace the pandas-based snippet with CLI usage:
   - `uv run giant check-data tcga`
   - `uv run giant check-data tcga_expert_vqa`
   - `uv run giant check-data tcga_slidebench`
   - `uv run giant check-data gtex`
   - `uv run giant check-data panda`

2. If a Python snippet is still desired, rewrite using stdlib:
   - `csv.DictReader` + `pathlib.Path`
   - Use `giant.eval.wsi_resolver.WSIPathResolver` for parity with runtime behavior.

## Acceptance Criteria

- All “Verification” instructions in `docs/DATA_ACQUISITION.md` run on a fresh `uv sync` without extra installs.
- Verification instructions correctly handle `gdc-client` TCGA layout (per-`file_id` subdirectories).
