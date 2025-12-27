# BUG-033: `make benchmark` Uses Wrong CLI Args (Dataset vs Path)

## Severity: P0 (Blocks benchmark runs via Makefile)

## Status: ✅ Fixed (2025-12-26)

## Summary

`make benchmark` currently calls `uv run giant benchmark ./data/multipathqa --output-dir ./results`, but `giant benchmark` expects a **dataset name** (`tcga`, `gtex`, `panda`, `tcga_expert_vqa`, `tcga_slidebench`). This blocks the intended “one-command” reproduction workflow and causes confusing failures (often a `ConfigError` for missing API keys before the dataset validation error).

## Repro

```bash
make benchmark
```

Observed:
- `dataset` is passed as `./data/multipathqa` (invalid).
- If `OPENAI_API_KEY` is missing, the command fails before reporting the invalid dataset.

## Root Cause

- Drift between Spec-12 CLI (`giant benchmark <dataset>`) and the `Makefile`/docs example.
- `src/giant/cli/runners.py:run_benchmark()` constructs an LLM provider (requiring API keys) before validating `dataset`.

## Proposed Fix

1. **Makefile**
   - Change `benchmark` target to accept a dataset name and include explicit `--csv-path`/`--wsi-root`.
   - Recommended pattern:
     - `DATASET ?= tcga`
     - `uv run giant benchmark $(DATASET) --csv-path data/multipathqa/MultiPathQA.csv --wsi-root data/wsi --output-dir results`
   - Optionally add convenience targets: `benchmark-tcga`, `benchmark-gtex`, `benchmark-panda`, etc.

2. **Docs**
   - Update `docs/specs/spec-01-foundation.md` and `AGENTS.md` to match the corrected command.

3. **CLI Runner Fail-Fast**
   - In `src/giant/cli/runners.py:run_benchmark()`, validate `dataset in BENCHMARK_TASKS` **before** `create_provider(...)` so invalid datasets error without requiring API keys.

## Acceptance Criteria

- `make benchmark` passes a valid dataset name (default `tcga` or via `DATASET=...`).
- `uv run giant benchmark not_a_dataset ...` fails with “Unknown dataset …” even when API keys are missing.

## Test Plan

- Unit: add a test that calls the benchmark runner with an invalid dataset and asserts it raises a dataset error (not `ConfigError`).
- Manual: run `make --dry-run benchmark DATASET=tcga` (or add a `benchmark-help` / `benchmark-smoke` target) to confirm argument wiring.
