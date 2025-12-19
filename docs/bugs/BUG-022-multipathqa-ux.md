# BUG-022: MultiPathQA Dataset Acquisition UX Gaps (Validation/Tooling)

## Severity: P4 (UX / Tooling)

## Status: Open

## Description
The paper describes MultiPathQA as being released publicly on HuggingFace. In practice (and in this repository), HuggingFace hosts the **metadata CSV**; the **WSIs themselves** must be obtained from TCGA / GTEx / PANDA sources and placed under `--wsi-root`.

This is documented (e.g., Spec-10 explicitly calls out metadata-only download), but the CLI/tooling does not currently provide strong “batteries included” helpers for:
- validating a local `--wsi-root` against `MultiPathQA.csv`,
- reporting which files are missing and where they’re expected,
- generating manifests / commands for common download workflows (e.g., `gdc-client` layout).

## Why This Matters
- Reduces time-to-first-run for new users.
- Avoids confusing “file not found” errors by catching missing/incorrect layout up front.

## Evidence
- `src/giant/data/download.py` downloads MultiPathQA CSV metadata only (by design).
- `docs/specs/spec-10-evaluation.md` notes WSIs may need to be acquired separately.
- `src/giant/eval/runner.py` resolves `image_path` under `--wsi-root` and errors when missing.

## Proposed Fix
1. Add a `giant check-data` (or `giant data validate`) command that:
   - loads `MultiPathQA.csv`,
   - checks that each referenced `image_path` exists under `--wsi-root`,
   - prints a summary + optionally writes a “missing files” report.
2. Add docs/scripts to generate:
   - TCGA `gdc-client` manifests from the CSV (where possible),
   - a recommended directory layout and disk-space expectations.
