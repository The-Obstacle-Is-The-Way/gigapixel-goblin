# BUG-038: Comprehensive E2E Bug Audit

**Status**: OPEN - AWAITING SENIOR REVIEW
**Severity**: MIXED (see table below)
**Audit Date**: 2025-12-29
**Audited By**: 8 parallel swarm agents
**Cost Impact**: $73.38 wasted on PANDA benchmark run

---

## Executive Summary

Comprehensive codebase audit discovered **12 bugs** across 8 audit domains:

| Severity | Count | Impact |
|----------|-------|--------|
| **CRITICAL** | 2 | Directly affects benchmark accuracy |
| **HIGH** | 3 | Causes failures or incorrect costs |
| **MEDIUM** | 5 | Edge cases, robustness issues |
| **LOW** | 2 | Documentation, design issues |

**Primary Finding**: PANDA benchmark reports 9.4% accuracy but should report ~24% due to extraction bug that discards 17 correct answers.

---

## Bug Summary Table

| ID | File | Line | Severity | Description |
|----|------|------|----------|-------------|
| **B1** | `answer_extraction.py` | 41-48 | CRITICAL | `isup_grade: null` not mapped to Grade 0 |
| **B2** | `openai_client.py` | 245 | CRITICAL | JSON "Extra data" error on trailing LLM text |
| **B3** | `answer_extraction.py` | 126-142 | HIGH | Naive brace-matching JSON extraction |
| **B4** | `anthropic_client.py` | 97 | HIGH | Silent JSON parsing failure in tool use |
| **B5** | `openai_client.py` | 270-272 | HIGH | Potential crash on None token counts |
| **B6** | `context.py` | 159 | MEDIUM | Off-by-one in step guard |
| **B7** | `runner.py` | 274-431 | MEDIUM | Asymmetric retry counter logic |
| **B8** | `converters.py` | 260-268 | MEDIUM | Empty base64 not caught early |
| **B9** | `runner.py` | 444-450 | MEDIUM | Recursive retry handling (bounded) |
| **B10** | `openai_client.py` | 105-107 | MEDIUM | Unknown action types pass unchecked |
| **B11** | `context.py` | 268 | LOW | Misleading comment on step index |
| **B12** | `protocol.py` | 129-137 | LOW | Empty Message.content allowed |

---

## CRITICAL BUGS

### B1: PANDA `isup_grade: null` Not Mapped to Grade 0

**Location**: `src/giant/eval/answer_extraction.py:41-48`

**Problem**: When LLM correctly determines "no cancer", it returns `{"isup_grade": null}`. The code crashes on `int(None)`, catches the exception, and returns `None` as extraction failure instead of Grade 0.

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

**Impact**:
- 47/197 PANDA items (23.9%) fail extraction
- 17/47 were actually CORRECT (ground truth = Grade 0)
- Current accuracy: 9.4% → With fix: ~24% (paper baseline: 23.2%)
- Cost wasted: $73.38

**Fix**:
```python
grade = obj.get("isup_grade")
if grade is None:
    return 0  # Clinical: null = no cancer = ISUP Grade 0
return int(grade)
```

---

### B2: JSON "Extra Data" Error on Trailing LLM Text

**Location**: `src/giant/llm/openai_client.py:245`

**Problem**: LLM sometimes outputs explanatory text after JSON object:
```
{"reasoning": "...", "action": {...}} I hope this helps explain my reasoning.
```
Python's `json.loads()` fails with "Extra data" error.

**Impact**:
- TCGA: 6/221 items (2.7%)
- GTEx: 6/191 items (3.1%)
- PANDA: 6/197 items (3.0%)
- **Total: 18/609 items (3.0%) fail across ALL benchmarks**

**Fix**: Extract first complete JSON object before parsing:
```python
def _extract_first_json_object(text: str) -> dict:
    match = re.search(r'\{(?:[^{}]|\{[^{}]*\})*\}', text)
    if not match:
        raise ValueError("No JSON object found")
    return json.loads(match.group())
```

---

## HIGH SEVERITY BUGS

### B3: Naive Brace-Matching JSON Extraction

**Location**: `src/giant/eval/answer_extraction.py:126-142`

**Problem**: Uses `find("{")` and `rfind("}")` without proper nesting consideration. Breaks on text with multiple JSON objects.

**Example failure**:
```
Here's my reasoning: {"step": 1} and action: {"action_type": "crop", "x": 100}
```
Would extract invalid content spanning both objects.

---

### B4: Silent JSON Parsing Failure in Anthropic Client

**Location**: `src/giant/llm/anthropic_client.py:97`

**Problem**: `json.JSONDecodeError` caught and suppressed with `pass`. Malformed action strings silently fail, producing confusing Pydantic errors.

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

### B6: Off-by-One in Step Guard

**Location**: `src/giant/agent/context.py:159`

**Problem**: Step guard uses `>=` check before increment, creating subtle timing issue.

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

### Cost Tracking Accuracy: VERIFIED

The $73.38 PANDA cost is **accurate**:
- Total tokens: 20,340,343
- Token split: 84.8% input / 15.2% output
- Recalculated: $73.3823 (perfect match)
- **NOTE**: Image costs appear to NOT be added (possible OpenAI API behavior)

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
1. **B1**: Fix `_extract_panda_label()` null handling
2. **B2**: Add JSON extraction before `json.loads()`

### Short-term
3. **B3**: Improve JSON extraction with proper brace counting
4. **B4**: Add logging for Anthropic JSON parse failures
5. Add missing test cases

### Long-term
6. Separate error counters for LLM vs validation errors
7. Add defensive None checks for token counts
8. Document edge cases

---

## Sign-Off Checklist

- [ ] **B1**: Fix `_extract_panda_label()` to map null -> 0
- [ ] **B2**: Add JSON extraction robustness in `openai_client.py`
- [ ] Add unit tests for PANDA null case
- [ ] Add unit tests for JSON trailing text
- [ ] Review and approve remaining medium/low fixes
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

### Agent 7: Cost Tracking Audit
- Verified $73.38 is accurate
- Noted image costs not added (API behavior)

### Agent 8: Metrics Audit
- Confirmed balanced accuracy is correct
- Explained 9.4% vs 14.6% discrepancy
