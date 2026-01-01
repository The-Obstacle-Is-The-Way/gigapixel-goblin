# BUG-039: Comprehensive Swarm Audit (8-Agent) — Senior Review

**Status**: COMPLETED ✅ (Critical + High triage done)
**Audit Date**: 2025-12-30
**Senior Review Date**: 2025-12-30
**Scope**: This document is SSOT for C1–C6 + H1–H12 only. Everything else below is an *unvalidated lead list* from the swarm and must not be treated as confirmed bugs without reproduction.

## Summary

- **Critical**: **C1, C3, C4, C5, C6 fixed**; **C2 retracted** (false positive).
- **High**: **H1, H2, H4, H6, H7, H9, H11 fixed**; **H3, H5, H8, H10, H12 retracted** (not bugs / already-correct behavior).

## Critical Bugs (C1–C6)

| ID | Status | What was wrong (validated) | Fix (current behavior) | Test coverage |
|----|--------|----------------------------|------------------------|---------------|
| C1 | ✅ FIXED | PANDA parse failures (no JSON / malformed JSON) did not always fall back to integer extraction | `extract_label()` falls through to `_extract_integer()` on PANDA JSON extraction exceptions only | `tests/unit/eval/test_answer_extraction.py::TestExtractLabelEdgeCases::test_panda_malformed_json_falls_back_to_integer` |
| C2 | ⚠️ RETRACTED | Claimed “budget race” in CLI benchmark loop | Not a bug: loop is sequential; budget is checked before and after each run | N/A |
| C3 | ✅ FIXED | Concurrent evaluation workers could overshoot budget | Budgeted evaluation is now **single-worker only** (`EvaluationConfig` validation), eliminating multi-worker in-flight overruns; worker loop still checks `stop_event` under lock | `tests/unit/eval/test_runner.py::TestEvaluationConfigValidation::test_budget_requires_single_worker` |
| C4 | ✅ FIXED | Empty/whitespace options match everything (`"" in text` is True) | Option-text matching skips empty/whitespace options | `tests/unit/eval/test_answer_extraction.py::TestExtractLabelEdgeCases::test_empty_option_does_not_match_everything` |
| C5 | ✅ FIXED | `benchmark_name` comparisons were case-sensitive in extraction | `extract_label()` normalizes `benchmark_name` via `.lower()` | `tests/unit/eval/test_answer_extraction.py::TestExtractLabelEdgeCases::test_benchmark_name_case_insensitive_panda` |
| C6 | ✅ FIXED | DICOM directory resolver selected an arbitrary `.dcm` without verifying series consistency | Resolver validates all `.dcm` files share one `SeriesInstanceUID`; mismatches raise a loud error | `tests/unit/eval/test_runner.py::TestResolveWsiPath::test_resolves_dicom_directory_multiple_series_raises` |

## High Severity (H1–H12)

| ID | Status | What was wrong (validated) | Fix (current behavior) | Test coverage |
|----|--------|----------------------------|------------------------|---------------|
| H1 | ✅ FIXED | Truth labels were not validated against benchmark constraints | `_parse_truth_label()` enforces 1-based option bounds (and PANDA 0–5) | `tests/unit/eval/test_runner.py::TestTruthLabelParsing::test_rejects_out_of_range_label_with_options` |
| H2 | ✅ FIXED | `is_valid` CSV column not stripped before comparison | `load_benchmark_items()` uses `.strip().lower()` for `is_valid` | `tests/unit/eval/test_runner.py::TestLoadBenchmarkItems::test_is_valid_with_trailing_whitespace_is_respected` |
| H3 | ⚠️ RETRACTED | Claimed majority-vote ties were non-deterministic | Already deterministic: `_select_majority_prediction()` uses “first seen in input order” tie-break | `tests/unit/eval/test_runner.py::TestMajorityVote::test_votes_on_labels_when_available` |
| H4 | ✅ FIXED | Concurrency + budget could overspend massively | `EvaluationConfig` forbids `budget_usd` with `max_concurrent != 1` (fail fast) | `tests/unit/eval/test_runner.py::TestEvaluationConfigValidation::test_budget_requires_single_worker` |
| H5 | ⚠️ RETRACTED | Claimed “forced summary” uninitialized and context lost at max steps | `forced_summary` is initialized (`None`) and `_force_final_answer()` builds a summary when not provided; no crash | N/A |
| H6 | ✅ FIXED | Memory guard only limited max dimension, not total pixel area | `CropEngine.crop()` now also enforces a max pixel-count guard (default 40,000,000) | `tests/unit/core/test_crop_engine.py::TestCropEngineHugeRegionProtection::test_rejects_region_exceeding_default_pixel_limit` |
| H7 | ✅ FIXED | Anthropic tool_use input could be `None` → AttributeError → wrapped as LLMError | Anthropic client validates tool input is a dict and raises `LLMParseError` | `tests/unit/llm/test_anthropic.py::TestAnthropicProviderGenerate::test_parse_error_on_none_tool_input` |
| H8 | ⚠️ RETRACTED | Claimed base64 image data not validated before cost calc | Already validated via `base64.b64decode(..., validate=True)` + image decode; unit tests exist | `tests/unit/llm/test_converters.py::TestCountImagePixelsInMessages::test_invalid_base64_raises` |
| H9 | ✅ FIXED | OpenAI empty output text raised a confusing JSON parse error | OpenAI client now raises a clear `LLMParseError("Empty output text…")` | `tests/unit/llm/test_openai.py::TestOpenAIProviderGenerate::test_parse_error_on_empty_output_text` |
| H10 | ⚠️ RETRACTED | Claimed CLI cost tracking misses image costs | Provider `usage.cost_usd` already includes image cost; CLI sums `total_cost` from runs | `tests/unit/llm/test_openai.py::TestOpenAIProviderGenerate::test_cost_calculation_includes_images` |
| H11 | ✅ FIXED | Checkpoint resume did not guard against resuming with a different model/provider | Checkpoints now persist and validate `model_name` + `provider_name` | `tests/unit/eval/test_resumable.py::TestCheckpointManager::test_load_or_create_existing_model_mismatch_raises` |
| H12 | ⚠️ RETRACTED | Claimed Windows path traversal checks incomplete | Existing validation rejects absolute paths / drives and `..` segments; Windows-style traversal does not bypass on supported platforms | `tests/unit/eval/test_runner.py::TestResolveWsiPath::test_rejects_path_traversal` |

## Implementation Notes (Design Decisions)

- **Budget enforcement**: With unknown per-item cost, strict enforcement with concurrency is not possible without reservations/estimation. The chosen fix is to **require sequential execution** whenever `budget_usd` is provided.
- **DICOM series validation**: Implemented using `pydicom` with `stop_before_pixels=True` and `specific_tags=["SeriesInstanceUID"]` for fast header-only reads.

## Verification (Local)

Run these after checkout:

```bash
uv run pytest tests/unit
uv run ruff check .
uv run mypy src/giant
```

## Unvalidated Swarm Leads (Not SSOT)

The swarm reported additional medium/low “possible issues”. These have **not** been reproduced or validated and are listed only as triage leads:

- Medium/Low lists were present in the original swarm report; re-run a focused audit before treating any as a bug.

## Sign-Off Checklist

- [x] C1–C6 triaged (fixed or retracted)
- [x] H1–H12 triaged (fixed or retracted)
- [x] Unit tests added for each fix
- [x] Full test suite passes (`uv run pytest tests/unit`)
- [x] Lint passes (`uv run ruff check .`)
- [x] Typecheck passes (`uv run mypy src/giant`)
