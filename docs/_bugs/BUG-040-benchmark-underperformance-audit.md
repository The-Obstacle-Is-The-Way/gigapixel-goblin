# BUG-040: Comprehensive Benchmark Underperformance Audit

**Date**: 2026-01-01
**Auditors**: 13-agent swarm (8 codebase + 5 paper review)
**Status**: AUDITED - Findings validated; P1-2 fixed; benchmark rerun pending

## Executive Summary

Launched comprehensive swarm audit to investigate why SlideBench (51.8%), TCGA (26.2%), and PANDA (20.3%) are underperforming compared to paper reported results.

**Key Finding**: The primary bottleneck is **model reasoning quality**, not navigation mechanics. Navigation depth is NOT correlated with accuracy - correct items in PANDA actually use MORE steps (10.79) than incorrect ones (10.09).

## Critical Findings (P0)

### P0-1: GTEx Data Downloaded from Wrong Source ❌ FALSE POSITIVE

**Location**: `data/wsi/gtex/`
**Reality check**:
- The GTEx slides are valid **DICOM WSI** (VL Whole Slide Microscopy Image Storage). `file(1)` reports “Big TIFF”, but `pydicom.dcmread(...).SOPClassUID` confirms DICOM WSI.
- Our resolver explicitly supports IDC-style GTEx layouts (`gtex/<GTEX-ID>/*.dcm`) via `WSIPathResolver._try_resolve_dicom_directory` in `src/giant/eval/wsi_resolver.py:111-175`.

**Verdict**: NOT A BUG. Source/extension mismatch does not break GTEx loading.

### P0-2: PANDA Class Collapse to Label 0 ✅ CONFIRMED (MODEL LIMITATION)

**Location**: `results/panda_giant_openai_gpt-5.2_results.json`
**Evidence**:
```text
Predicted: Label 0 = 78.2% (154/197)
Truth:     Label 0 = 27.4% (54/197)
Gap:       +50.8 percentage points over-prediction of benign
```
**Impact**: Model is systematically biased toward benign diagnosis - calling 78% of cases "no cancer" when only 27% are actually benign
**Additional note**: 115/154 label-0 predictions are emitted as `"isup_grade": null` and mapped to grade 0 by our extractor (intentional BUG-038 B1 behavior in `src/giant/eval/answer_extraction.py:45-67`).

**Verdict**: Not a code bug; underperformance is primarily model/prompt behavior.

### P0-3: TCGA Label Bias (Labels 5, 19 Dominate) ✅ CONFIRMED (MODEL LIMITATION)

**Location**: `results/tcga_giant_openai_gpt-5.2_results.json`
**Evidence**:
```text
Top predictions:
  Label 5:  21.3% predicted (47/221) vs ~5% truth
  Label 19: 14.0% predicted (31/221) vs 8.1% truth
  Label 4:  10.9% predicted (24/221) vs 5.4% truth

Total: 35.3% of predictions go to just 2 labels
Accuracy: 61/221 = 27.6%
```
**Impact**: Model over-predicts certain cancer types, 30-way classification is very hard
**Verdict**: Not a code bug; this reflects task/model difficulty.

### P0-4: Truth Label Parsing Ambiguity (SlideBench/ExpertVQA) ❌ FALSE POSITIVE

**Code**: `src/giant/eval/loader.py:123-168` parses `answer` as `int` before label matching.

**Why it’s not a bug (for MultiPathQA)**:
- MultiPathQA explicitly defines `answer` for `tcga`, `tcga_slidebench`, and `tcga_expert_vqa` as a **1-based index into `options`** (`data/multipathqa/DATASET_CARD.md:183`), so integer-first parsing is correct for the benchmark this repo targets.

**Verdict**: NOT A BUG in the current benchmark contract.

### P0-5: OpenAI NULL Value Handling ❌ FALSE POSITIVE (reframed)

**Reality check**:
- `_normalize_openai_response()` already drops irrelevant nullable fields (e.g., `answer_text=None` on crop) and is regression-tested in `tests/unit/llm/test_openai.py`.
- The real OpenAI reliability gap is **schema permissiveness vs Pydantic constraints** (see P1-2).

**Verdict**: Not a bug as stated; superseded by P1-2.

## High Priority Findings (P1)

### P1-1: Coordinate Truncation in Transforms ❌ FALSE POSITIVE (expected behavior)

**Code**: `src/giant/wsi/types.py:163-246` uses truncation for coordinate/size transforms.

**Why it’s not a bug**:
- Unit tests explicitly codify truncation + round-trip error tolerance (`tests/unit/wsi/test_types.py:117-157`).
- Changing to `round()` would be a behavior change requiring a dedicated design decision + benchmark justification.

**Verdict**: NOT A BUG.

### P1-2: OpenAI Schema Missing Constraints ✅ FIXED

**Location**: `src/giant/llm/schemas.py` (`step_response_json_schema_openai`)

**Issue**: OpenAI schema is looser than `src/giant/llm/protocol.py`, allowing values that later fail Pydantic validation:
- `reasoning` missing `minLength: 1`
- `x/y` allow negatives (missing `minimum: 0`)
- `width/height` allow 0/negatives (missing `exclusiveMinimum: 0`)
- `hypotheses` allows empty arrays (missing `minItems: 1`)

**Evidence**:
- `results/tcga_slidebench_giant_openai_gpt-5.2_results.json` item `572`: `action.crop.y = -22000` caused `LLMParseError` after max retries.

**Spec**: `docs/_specs/BUG-040-P1-2-openai-stepresponse-schema-hardening.md` (IMPLEMENTED)

**Fix implemented**:
- Hardened OpenAI schema constraints in `src/giant/llm/schemas.py` (aligns with Pydantic `StepResponse` + action models).
- Added unit coverage: `tests/unit/llm/test_openai.py::TestBuildJsonSchema::test_schema_enforces_pydantic_field_constraints`.

**Verdict**: ✅ FIXED (was a confirmed code bug).

### P1-3: Agent Orchestration Step Counting Issues ⚠️ ALREADY FIXED (BUG-038)

**Audit**:
- Current step counting (`ContextManager.current_step = len(turns) + 1`) is consistent with message construction and max-step enforcement (`src/giant/agent/context.py:67-197`, `src/giant/agent/runner.py:316-355`).
- Retry-counter reset + iterative invalid-region recovery were fixed in BUG-038 (see `docs/_archive/bugs/BUG-038-B7-retry-counter-logic.md` and BUG-038 notes).

**Verdict**: No remaining issue found.

### P1-4: Prompt Instructions Removed on Subsequent Steps ❌ FALSE POSITIVE

**Location**: `src/giant/prompts/templates.py`
**Audit**:
- The system prompt is included every step (`ContextManager.get_messages` always emits it).
- Subsequent user prompts still contain an instructions block (`src/giant/prompts/templates.py:83-95`).

**Verdict**: NOT A BUG.

### P1-5: One TCGA File Truncated During Download ❌ FALSE POSITIVE (no evidence)

**Location**: `data/wsi/tcga/` (specific file TBD)
**Audit**:
- No TCGA benchmark failures indicate WSI corruption; TCGA failures in saved artifacts are OpenAI parse failures (`results/tcga_giant_openai_gpt-5.2_results.json`).

**Verdict**: Unsubstantiated in this repo.

### P1-6: PANDA Benchmark Errors (JSON parse / invalid crops) ⚠️ ALREADY FIXED (BUG-038)

**Audit**:
- The dominant `"Extra data"` JSON parse failure mode is fixed by BUG-038 B2 (`src/giant/llm/openai_client.py:268-279`), but the saved benchmark artifacts were generated pre-fix and still contain those failures.
- Invalid crop regions appear frequently in logs but are generally recovered via the agent’s invalid-region loop; they do not appear as item-level errors in `results/panda_giant_openai_gpt-5.2_results.json`.

**Verdict**: Fixed in code; rerun benchmarks to remove pre-fix artifact failures.

### P1-7: Overlay Coordinate Label Double-Truncation ❌ FALSE POSITIVE

**Location**: `src/giant/geometry/overlay.py`
**Audit**:
- Guide placement + label coordinate computation use integer pixel alignment (`int(...)`), and label formatting is `str(coord)` (no additional truncation pass).

**Verdict**: NOT A BUG (at most a minor precision enhancement).

### P1-8: size_at_level Minimum Clamping ❌ FALSE POSITIVE

**Location**: `src/giant/wsi/types.py` or related
**Audit**:
- `size_at_level()` explicitly clamps each dimension to `>= 1` to avoid zero-sized OpenSlide reads (`src/giant/wsi/types.py:205-226`) and has unit coverage (`tests/unit/wsi/test_types.py:153-157`).

**Verdict**: NOT A BUG.

## Medium Priority Findings (P2)

### P2-1: Prompt Formatting Inconsistencies ❌ FALSE POSITIVE

**Location**: `src/giant/prompts/`
**Audit**: Only two prompt template files exist (`templates.py`, `builder.py`); no functional inconsistency found.

### P2-2: PANDA Fallback Extraction Chain Implicit ⚠️ ALREADY FIXED (BUG-038)

**Location**: `src/giant/eval/answer_extraction.py`
**Audit**:
- PANDA null-handling + fallback behavior are explicit and regression-tested (`tests/unit/eval/test_answer_extraction.py`).

### P2-3: TCGA Single-Sample Classes ✅ CONFIRMED (DATA LIMITATION)

**Location**: `data/multipathqa/MultiPathQA.csv`
**Evidence**: Some TCGA classes have only 1 sample
**Impact**: Balanced accuracy penalizes these classes heavily
**Verdict**: Not a code bug; a dataset property.

## Paper Implementation Gap Analysis

### Gap-1: Algorithm 1 Loop Semantics Differ

**Status**: Minor - our implementation follows paper intent but loop structure differs slightly
**Impact**: LOW

### Gap-2: Missing Provider-Specific System Prompts

**Status**: Framework exists (`GIANT_SYSTEM_PROMPT*` env vars) but verbatim paper prompts not included
**Impact**: MEDIUM - may affect reproduction

### Gap-3: CONCH Integration Framework Only

**Status**: Code scaffolding exists but model weights not included (gated by license)
**Impact**: LOW - documented limitation

## Recommendations

### Immediate Actions

1. **Harden OpenAI `StepResponse` schema** - ✅ implemented (`docs/_specs/BUG-040-P1-2-openai-stepresponse-schema-hardening.md`)
2. **Re-run benchmarks with BUG-038 fixes** - remove pre-fix `"Extra data"` failures and re-measure against paper baselines
3. **Investigate PANDA benign bias** - prompt/model work (confirmed model limitation)
4. **Paper prompt reproduction** - consider adding verbatim provider-specific system prompts once Supplementary Material is available (Gap-2)

### Before Next Benchmark Run

1. Ensure runs use post-BUG-038 code paths (notably OpenAI trailing-text JSON parsing + PANDA null handling).
2. Decide whether to keep/remove 2025 prompt enhancements for strict paper reproduction (Gap-2).

### Low Priority Cleanup

1. Document dataset limitations (e.g., TCGA singleton classes) alongside balanced-accuracy reporting.

## Appendix: Agent Results Summary

| Agent | Focus Area | P0 | P1 | P2 | Key Finding | Verified |
|-------|------------|----|----|----|-|----------|
| 1 | Data Integrity | 1 | 2 | 0 | GTEx format | ❌ False positive |
| 2 | CSV Schema | 0 | 1 | 1 | TCGA single-sample | ⚠️ Data limitation |
| 3 | Agent Orchestration | 0 | 3 | 0 | Retry/step logic | ⚠️ Already fixed (BUG-038) |
| 4 | LLM Parsing | 0 | 1 | 0 | OpenAI schema constraints | ✅ Confirmed |
| 5 | Benchmark Eval | 1 | 0 | 0 | Truth label parsing ambiguity | ❌ False positive |
| 6 | WSI Processing | 0 | 3 | 0 | Coordinate truncation | ❌ False positive |
| 7 | Prompt Engineering | 0 | 1 | 2 | Instructions removed | ❌ False positive |
| 8 | Results Analysis | 2 | 0 | 0 | Class collapse/bias | ✅ Model limitation |
| 9-13 | Paper Review | 0 | 0 | 3 | Minor gaps | ⚠️ Known |

## Validated Findings Summary

| ID | Issue | Verdict | Action Required |
|----|-------|--------|-----------------|
| P0-1 | GTEx “wrong source/extension” | ❌ FALSE POSITIVE | None |
| P0-2 | PANDA label-0 collapse | ✅ CONFIRMED (model limitation) | Prompt/model work |
| P0-3 | TCGA label bias | ✅ CONFIRMED (model limitation) | Prompt/model work |
| P0-4 | Truth label parsing ambiguity | ❌ FALSE POSITIVE | None |
| P0-5 | OpenAI NULL handling | ❌ FALSE POSITIVE | None (see P1-2) |
| P1-1 | Coordinate truncation | ❌ FALSE POSITIVE | None |
| P1-2 | OpenAI schema constraint mismatch | ✅ CONFIRMED (fixed) | Rerun benchmarks to quantify impact |
| P1-3 | Agent step/retry issues | ⚠️ ALREADY FIXED | None |
| P1-4 | Subsequent prompts omit instructions | ❌ FALSE POSITIVE | None |
| P1-5 | Truncated TCGA file | ❌ FALSE POSITIVE | None |
| P1-6 | PANDA parse/crop “errors” | ⚠️ ALREADY FIXED | Rerun benchmarks to clear pre-fix artifacts |
| P1-7 | Overlay double truncation | ❌ FALSE POSITIVE | None |
| P1-8 | `size_at_level` min clamp | ❌ FALSE POSITIVE | None |
| P2-1 | Prompt formatting | ❌ FALSE POSITIVE | None |
| P2-2 | PANDA fallback chain implicit | ⚠️ ALREADY FIXED | None |
| P2-3 | TCGA singleton classes | ✅ CONFIRMED (data limitation) | None |

**Conclusion**: Benchmark underperformance is still primarily due to **model reasoning limitations**, but the saved benchmark artifacts also include **pre-BUG-038** OpenAI parse failures. The only confirmed code change from this audit was OpenAI schema hardening (P1-2), now implemented; several previously listed “bugs” were false positives or already fixed in BUG-038.
