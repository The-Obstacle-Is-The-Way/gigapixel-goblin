# BUG-038: Comprehensive E2E Bug Audit

**Status**: CRITICAL BUGS FIXED (B1, B2) - Other bugs deferred
**Severity**: MIXED (see table below)
**Audit Date**: 2025-12-29
**Fix Date**: 2025-12-29
**Audited By**: 8 parallel swarm agents
**Cost Impact**: Reported $73.38 spent on PANDA benchmark run (lower bound; see Cost Notes)

---

## Executive Summary

Comprehensive codebase audit produced **12 findings** across 8 audit domains:

| Category | Count | Impact |
|----------|-------|--------|
| **CRITICAL** | 2 | Directly affects benchmark scoring / completion |
| **HIGH** | 3 | Robustness + error clarity + defensive guards |
| **MEDIUM** | 4 | Edge cases, retry semantics, robustness issues |
| **LOW** | 2 | Documentation / validation ergonomics |
| **RETRACTED** | 1 | Not a bug after review |

**Primary Findings (verified against current code + saved run artifacts):**
- PANDA reports **9.4% balanced accuracy** largely because `"isup_grade": null` is not mapped to benign label 0; rescoring the existing run with only the B1 fix yields **~19.8% balanced accuracy** (still includes 6 hard failures from B2).
- OpenAI `"Extra data"` parse failures block **18/609 items (3.0%)** across all benchmarks and trigger frequent retries (see log counts in B2), which also **undercounts spend** because parse-failed calls do not accumulate `usage`.

---

## Finding Summary Table

| ID | Location | Severity | Status | Description |
|----|----------|----------|--------|-------------|
| **B1** | `src/giant/eval/answer_extraction.py:41-48` | CRITICAL | **FIXED** | PANDA `"isup_grade": null` now maps to label 0 (benign); out-of-range grades return None without fallback |
| **B2** | `src/giant/llm/openai_client.py:245` | CRITICAL | **FIXED** | Uses `json.JSONDecoder().raw_decode()` to ignore trailing text after JSON |
| **B3** | `src/giant/eval/answer_extraction.py:126-142` | HIGH | CONFIRMED | Naive JSON extraction via `find`/`rfind` (should use decoder-based parsing) |
| **B4** | `src/giant/llm/anthropic_client.py:91-99` | HIGH | IMPROVEMENT | Invalid JSON in stringified `action` loses root cause (decode error swallowed; pydantic error is less specific) |
| **B5** | `src/giant/llm/openai_client.py:270-272`, `src/giant/llm/anthropic_client.py:247-249` | HIGH | DEFENSIVE | Guard against `usage.*_tokens is None` (TypeError today) |
| **B6** | `src/giant/agent/context.py:159` | — | RETRACTED | Step guard is correct and unit-tested; no off-by-one bug found |
| **B7** | `src/giant/agent/runner.py:270-437` | MEDIUM | REVIEW | Retry/error counter semantics are hard to reason about; may prematurely exhaust retries |
| **B8** | `src/giant/llm/converters.py:260-268` | MEDIUM | CONFIRMED | Empty base64 (`""`) decodes to zero bytes and fails later in `Image.open()` |
| **B9** | `src/giant/agent/runner.py:444-450` | MEDIUM | IMPROVEMENT | Recursive retry for invalid crops (bounded, but avoidable) |
| **B10** | `src/giant/llm/openai_client.py:105-107` | MEDIUM | IMPROVEMENT | Unknown action types produce pydantic discriminator errors; can raise clearer `LLMParseError` |
| **B11** | `src/giant/agent/context.py:268` | LOW | IMPROVEMENT | Misleading comment on user message index vs step number |
| **B12** | `src/giant/llm/protocol.py:129-137` | LOW | IMPROVEMENT | Consider `min_length=1` for `Message.content` to prevent empty API payloads |

---

## CRITICAL BUGS

### B1: PANDA `isup_grade: null` Not Mapped to Grade 0

**Location**: `src/giant/eval/answer_extraction.py:41-48`

**Problem**: When the model indicates benign/no cancer, PANDA predictions frequently include `{"isup_grade": null}`. Current extraction raises `TypeError` on `int(None)`, returns `None`, and then `extract_label()` falls back to naive integer parsing (often grabbing coordinate numbers), producing out-of-range or incorrect labels.

**Code**:
```python
def _extract_panda_label(text: str) -> int | None:
    try:
        json_str = _extract_json_object(text)
        obj = json.loads(json_str)
        return int(obj["isup_grade"])  # BUG: int(None) raises TypeError
    except Exception:
        return None  # Returns failure instead of 0
```

**Impact (from `results/panda_giant_openai_gpt-5.2_results.json`)**:
- `"isup_grade": null` appears in **115/197** PANDA predictions (58.4%)
  - 47/115 become `predicted_label=None` (extraction failures)
  - 68/115 are mis-parsed via integer fallback (including **32 out-of-range labels** like 1700)
- As-run PANDA metric: **9.4% ± 2.2% balanced accuracy** (`n_errors=6`, `n_extraction_failures=47`)
- Rescore-only with B1 fix (no new LLM calls): **~19.8% balanced accuracy**, **~28.4% raw accuracy** (still includes 6 B2 failures)

**Fix (must distinguish null vs missing key):**
```python
if "isup_grade" not in obj:
    return None
grade = obj["isup_grade"]
if grade is None:
    return 0  # Benign/no cancer = ISUP Grade 0
grade_int = int(grade)
return grade_int if 0 <= grade_int <= 5 else None
```

---

### B2: JSON "Extra Data" Error on Trailing LLM Text

**Location**: `src/giant/llm/openai_client.py:245`

**Problem**: LLM sometimes outputs explanatory text after JSON object:
```
{"reasoning": "...", "action": {...}} I hope this helps explain my reasoning.
```
Python's `json.loads()` fails with "Extra data" error.

**Impact (from results files)**:
- Hard failures (no prediction; max retries exceeded):
  - TCGA: 6/221 items (2.7%)
  - GTEx: 6/191 items (3.1%)
  - PANDA: 6/197 items (3.0%)
  - **Total: 18/609 items (3.0%)**
- Frequent transient parse failures (retried successfully):
  - `results/tcga-benchmark-20251227-084052.log`: 83 occurrences
  - `results/gtex-benchmark-20251227-010151.log`: 58 occurrences
  - `results/panda_benchmark.log`: 56 occurrences
- **Cost tracking is undercounted** today: parse-failed calls do not accumulate `usage`, and the 18 hard failures show `cost_usd=0`, `total_tokens=0` in results.

**Fix (robust; avoid regex brace matching):**
- Parse the first valid JSON object from `output_text` using `json.JSONDecoder().raw_decode()` (ignore trailing content).
- Validate against `StepResponse`; if the first JSON object is not a valid `StepResponse`, scan for the next JSON object and retry.
- (Optional but recommended) Accumulate `usage`/cost even when parsing fails, so retries reflect real spend.

---

## HIGH SEVERITY BUGS

### B3: Naive Brace-Matching JSON Extraction

**Location**: `src/giant/eval/answer_extraction.py:126-142`

**Problem**: Uses `find("{")` + `rfind("}")` which can span multiple JSON objects. Prefer decoder-based parsing (`raw_decode`) or scan-and-validate approach.

**Example failure**:
```
Here's my reasoning: {"step": 1} and action: {"action_type": "crop", "x": 100}
```
Would extract invalid content spanning both objects.

---

### B4: Silent JSON Parsing Failure in Anthropic Client

**Location**: `src/giant/llm/anthropic_client.py:97`

**Problem**: If Anthropic returns `tool_input["action"]` as a string, invalid JSON is caught and ignored. The subsequent pydantic error is still raised, but the root-cause (“action was a string but not valid JSON”) is not explicit.

**Code**:
```python
except json.JSONDecodeError:
    pass  # Let pydantic handle the validation error
```

---

### B5: Potential Crash on None Token Counts

**Location**: `src/giant/llm/openai_client.py:270-272` and `anthropic_client.py:247-249`

**Problem**: Token counts from SDK could theoretically be `None`:
```python
prompt_tokens = usage.input_tokens
completion_tokens = usage.output_tokens
total_tokens = prompt_tokens + completion_tokens  # TypeError if None
```

---

## MEDIUM SEVERITY BUGS

### B6: Off-by-One in Step Guard (RETRACTED)

**Location**: `src/giant/agent/context.py:159`

**Result**: Reviewed `ContextManager.get_messages()` and corresponding unit tests (`tests/unit/agent/test_context.py`). The step guard is correct for preventing a user step beyond `max_steps`. No fix required.

---

### B7: Asymmetric Retry Counter Logic

**Location**: `src/giant/agent/runner.py:274-431`

**Problem**: `_consecutive_errors` incremented in BOTH initial LLM call path AND retry error handling, causing compound counting.

---

### B8: Empty Base64 Not Caught Early

**Location**: `src/giant/llm/converters.py:260-268`

**Problem**: After None check, empty string `""` decodes successfully but produces zero bytes, potentially failing in `Image.open()`.

---

### B9: Recursive Retry Handling

**Location**: `src/giant/agent/runner.py:444-450`

**Problem**: Uses recursion via `await self._handle_crop()`. Bounded by `max_retries=3` so safe, but not ideal.

---

### B10: Unknown Action Types Pass Unchecked

**Location**: `src/giant/llm/openai_client.py:105-107`

**Problem**: Unknown action types passed through as-is without validation, producing confusing Pydantic errors instead of early LLMParseError.

---

## LOW SEVERITY ISSUES

### B11: Misleading Comment on Step Index

**Location**: `src/giant/agent/context.py:268`

Comment says `== step-1` but variable meaning is different. Cosmetic issue.

---

### B12: Empty Message.content Allowed

**Location**: `src/giant/llm/protocol.py:129-137`

`Message` model allows `content=[]` which would cause API errors. No validation prevents this.

---

## ADDITIONAL FINDINGS

### Cost Notes (Not Fully Verifiable From Saved Artifacts)

The results files are internally consistent (sum of per-item `cost_usd` equals `total_cost_usd`), but they are **not a reliable measure of actual spend** because:
- Parse-failed calls (B2) do not accumulate `usage` and are recorded as `cost_usd=0`, `total_tokens=0`.
- Transient parse failures (see B2 log counts) also represent extra API calls that are not reflected in costs.
- Prompt vs completion token split is not persisted in the saved artifacts, so external recomputation is limited.

### Metrics Calculation: CORRECT

- Balanced accuracy calculation is mathematically correct
- Bootstrap CI uses proper `ddof=1` for sample std
- Sentinel value `-1` never equals ground truth labels

### Data Schema: CORRECT

- CSV parsing handles multiple formats (JSON, Python literal, pipe-delimited)
- Type conversions are proper
- BenchmarkItem Pydantic model enforces integer truth_label

---

## TEST COVERAGE GAPS

Missing test cases identified:

1. **PANDA null value**: `'{"isup_grade": null}'`
2. **PANDA missing key**: `'{"reasoning": "test"}'`
3. **Empty system messages**: System message with no text content
4. **Unknown action types**: OpenAI returns `action_type="invalid"`
5. **None token counts**: SDK returns None for usage fields
6. **Empty Message.content**: Messages with `content=[]`

---

## FIX PRIORITY

### Immediate (Before next benchmark run)
1. **B1**: Fix `_extract_panda_label()` null → 0 (do not treat missing key as benign)
2. **B2**: Fix OpenAI `"Extra data"` parsing (decoder-based extraction + validate `StepResponse`)

### Short-term
3. **B3**: Replace brace matching with decoder-based JSON extraction helper (shared)
4. **B4**: Make Anthropic stringified-`action` decode errors explicit (raise/log root cause)
5. Add missing unit tests (PANDA null + missing-key; OpenAI trailing text)

### Long-term
6. **B7**: Clarify/adjust retry semantics (separate counters for LLM vs validation errors)
7. **B5**: Add defensive guards for `usage.*_tokens is None`
8. Document edge cases + invariants

---

## Sign-Off Checklist

- [x] **B1**: Fix `_extract_panda_label()` null → 0 (missing key remains failure) ✅ FIXED 2025-12-29
- [x] **B2**: Fix OpenAI `"Extra data"` parsing (ignore trailing text; validate `StepResponse`) ✅ FIXED 2025-12-29
- [x] Add unit tests for PANDA null + missing-key cases ✅ 4 new tests added
- [x] Add unit tests for OpenAI trailing-text JSON ✅ 2 new tests added
- [ ] Re-score PANDA run after B1 fix (no new LLM calls) to verify ~19.8% balanced accuracy
- [ ] Review and approve remaining medium/low fixes (B3-B12 deferred)
- [ ] Re-run PANDA benchmark with fix (optional, ~$73)
- [ ] Update benchmark-results.md with corrected analysis

---

## Appendix: Swarm Agent Reports

### Agent 1: Answer Extraction Audit
- Found B1, B3
- Verified 6+ missing test cases

### Agent 2: JSON Parsing Audit
- Found B2, B4
- Verified 18/609 items fail across all benchmarks

### Agent 3: Log Analysis
- Confirmed 198 total LLM call failures
- 92 invalid crop region warnings (handled correctly)

### Agent 4: LLM Client Audit
- Found B5, B10
- Verified error handling patterns

### Agent 5: Data Schema Audit
- Confirmed schema is sound
- Verified answer format handling is correct

### Agent 6: Agent Loop Audit
- Found B6, B7, B9
- Verified boundary conditions

### Agent 7: Cost Tracking Audit (UPDATED)
- Results-file totals are internally consistent, but absolute spend is likely undercounted due to B2 (parse-failed calls not costed).

### Agent 8: Metrics Audit (UPDATED)
- Balanced accuracy implementation is correct.
- The previously cited “14.6% balanced accuracy” is actually the **raw accuracy among scored items** (21 correct / 144 labeled); it is not balanced accuracy.
