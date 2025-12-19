# BUG-022: MultiPathQA Dataset Acquisition UX Gaps (Validation/Tooling)

## Severity: P4 (UX / Tooling)

## Status: Closed (Fixed)

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

## Resolution
Implemented `giant check-data <dataset>` to validate local WSI availability before running benchmarks.

Behavior:
- Checks **unique WSI files** referenced by `MultiPathQA.csv` for the selected benchmark.
- Exits `0` when all required WSIs are present; exits `1` when any are missing.
- `--json` returns counts + a small set of missing examples; `-v` prints missing examples in text mode.

Example:
`giant check-data tcga --csv-path data/multipathqa/MultiPathQA.csv --wsi-root data/wsi -v`

## Follow-ups (Optional)
- Add a `--report <path>` option to write full missing manifests for bulk download workflows (e.g., TCGA `gdc-client`).
