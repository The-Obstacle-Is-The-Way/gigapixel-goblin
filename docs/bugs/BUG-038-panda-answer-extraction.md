# BUG-038: PANDA Answer Extraction + Scoring Issues

**Status**: FIXED (B1, B2)
**Severity**: CRITICAL (was)
**Component(s)**:
- `src/giant/eval/answer_extraction.py` (B1)
- `src/giant/llm/openai_client.py` (B2; affects PANDA runs)
**Discovered**: 2025-12-29
**Fixed**: 2025-12-29
**Cost Impact**: Reported $73.38 for PANDA run (lower bound; parse-failed calls are not costed)

## Summary

The PANDA benchmark (Prostate grading, 6-way ISUP classification, labels 0–5) is currently distorted by two independent issues:

1) **B1 (answer extraction)**: PANDA JSON outputs frequently contain `"isup_grade": null` to represent benign/no cancer (label 0). Current extraction treats `null` as a failure and then falls back to naive integer extraction, which often grabs **coordinate numbers** and produces **out-of-range labels**.
2) **B2 (OpenAI structured output parsing)**: `OpenAIProvider` uses `json.loads(output_text)` and crashes with `Extra data` when the model appends trailing text after a valid JSON object. This causes retries (wasted spend) and **6/197 hard failures** in PANDA.

**Measured on current artifacts** (`results/panda_giant_openai_gpt-5.2_results.json`, `results/panda_benchmark.log`):
- As-run PANDA metric (balanced accuracy): **9.4% ± 2.2%** (`n_errors=6`, `n_extraction_failures=47`)
- `"isup_grade": null` appears in **115/197** PANDA predictions (58.4%)
  - 47/115 become `predicted_label=None` (extraction failure)
  - 68/115 are mis-parsed via integer fallback, including **32/68 out-of-range labels** (not in 0–5)
- Rescoring the existing PANDA predictions with only the B1 fix (no new LLM calls) yields:
  - Balanced accuracy ≈ **19.8%**
  - Raw accuracy ≈ **28.4%** (56/197 correct; still includes 6 B2 failures)

## Root Cause Analysis

### Primary Bug: `isup_grade: null` Not Mapped to Grade 0

When the LLM determines "no cancer detected", it returns a clinically accurate response:

```json
{
  "primary_pattern": null,
  "secondary_pattern": null,
  "total_score": null,
  "isup_grade": null
}
```

**Clinical / dataset context:** MultiPathQA PANDA uses labels 0–5 where **0 = benign/no cancer**. When the model indicates benign and emits `null`, the canonicalized label should be 0.

**Bug Location:** `_extract_panda_label()` in `answer_extraction.py:41-48`:

```python
def _extract_panda_label(text: str) -> int | None:
    """Extract ISUP grade from PANDA JSON response."""
    try:
        json_str = _extract_json_object(text)
        obj = json.loads(json_str)
        return int(obj["isup_grade"])  # <-- BUG: int(None) raises TypeError
    except Exception:
        return None  # <-- Returns None instead of 0
```

**Fix Required (must distinguish null vs missing key):**
```python
def _extract_panda_label(text: str) -> int | None:
    """Extract ISUP grade from PANDA JSON response."""
    try:
        json_str = _extract_json_object(text)
        obj = json.loads(json_str)
        if "isup_grade" not in obj:
            return None
        grade = obj["isup_grade"]
        if grade is None:
            return 0  # Benign/no cancer = ISUP Grade 0
        grade_int = int(grade)
        return grade_int if 0 <= grade_int <= 5 else None
    except Exception:
        return None
```

### Secondary Bug: JSON Parsing "Extra Data" Errors

6/197 PANDA items (3.0%) failed completely due to JSON parsing errors during agent execution:

```text
Max retries (3) exceeded: Failed to parse JSON: Extra data: line 1 column 355 (char 354)
```

**Root Cause:** The LLM sometimes outputs trailing text after the JSON object:
```text
{"reasoning": "...", "action": {...}} I hope this helps explain my reasoning.
```

Python's `json.loads()` fails with "Extra data" when there's content after the first complete JSON object.

**Affected Items (PANDA):** 9613, 8045, 255, 9307, 2626, 6761
**Affected Across All Benchmarks:**
- TCGA: 6/221 (2.7%)
- GTEx: 6/191 (3.1%)
- PANDA: 6/197 (3.0%)

**Bug Location:** `openai_client.py:245`:
```python
raw_data = json.loads(output_text)  # Fails on trailing text
```

**Fix Required (robust; avoid regex brace matching):**
- Parse the first **valid JSON object** from `output_text` (ignore trailing content) using `json.JSONDecoder().raw_decode()`.
- Validate against `StepResponse`; if the first JSON object is not a valid `StepResponse`, scan for the next JSON object and retry.
- **Cost accounting note**: today, parse-failed calls drop `usage` on the floor (and results show `cost_usd=0`, `total_tokens=0` for the 18 hard failures). Fixing B2 should also address undercounted spend.

## Data Analysis

### B1 Breakdown: `"isup_grade": null` Handling (PANDA)

| Category | Count | Percentage |
|----------|-------|------------|
| `"isup_grade": null` present in prediction | 115 | 58.4% |
| → extracted label `None` (failure) | 47 | 23.9% |
| → mis-parsed label via integer fallback | 68 | 34.5% |
| → (subset) out-of-range label (not 0–5) | 32 | 16.2% |

**Why this matters:** the 68 mis-parsed null-grade outputs are **not counted** as “extraction failures” today, but they still corrupt scoring (e.g., labels like 1700).

### Ground Truth for All `"isup_grade": null` Outputs (n=115)

| Ground Truth | Count | Model Correct? |
|--------------|-------|----------------|
| ISUP Grade 0 | 41 | Yes (null → 0) |
| ISUP Grade 1 | 27 | No (missed cancer) |
| ISUP Grade 2 | 11 | No (missed cancer) |
| ISUP Grade 3 | 15 | No (missed cancer) |
| ISUP Grade 4 | 11 | No (missed cancer) |
| ISUP Grade 5 | 10 | No (missed cancer) |

**Key Insight:** There are **41 benign (truth=0)** cases inside the null outputs; only 5/41 are currently scored as correct because the extractor drops into integer fallback.

### Rescore-Only Impact of the B1 Fix (No New LLM Calls)

Using the saved predictions in `results/panda_giant_openai_gpt-5.2_results.json` and only changing extraction (null → 0):

| Metric | As-Run | Rescore w/ B1 Fix |
|--------|--------|-------------------|
| Balanced Accuracy (paper-faithful; failures incorrect) | 9.4% | ~19.8% |
| Raw Accuracy (paper-faithful; failures incorrect) | 10.7% | ~28.4% |
| Grade 0 Recall | 24.1% (13/54) | ~90.7% (49/54) |

Note: This still includes the 6 hard failures caused by B2 (empty prediction / max retries exceeded).

## Per-Class Recall (Balanced Accuracy Components)

| ISUP Grade | Correct | Total | Accuracy |
|------------|---------|-------|----------|
| 0 (Benign) | 13 | 54 | 24.1% |
| 1 | 1 | 49 | 2.0% |
| 2 | 1 | 25 | 4.0% |
| 3 | 3 | 23 | 13.0% |
| 4 | 3 | 23 | 13.0% |
| 5 | 0 | 23 | 0.0% |

**After B1 fix (rescore-only):** Grade 0 recall jumps to ~90.7%; other classes remain low (model capability / prompting), and grade 3 recall drops slightly because “lucky” coordinate-number matches are removed.

## Reproduction

```bash
python3 - <<'PY'
import json
import re
from collections import Counter

path = "results/panda_giant_openai_gpt-5.2_results.json"
data = json.load(open(path))
results = data["results"]

isup_re = re.compile(r'"isup_grade"\\s*:\\s*(null|\\d+)')

def isup_value(prediction: str) -> int | None:
    m = isup_re.search(prediction)
    if not m:
        return None
    return None if m.group(1) == "null" else int(m.group(1))

n_total = len(results)
n_errors = sum(r["error"] is not None for r in results)
n_extraction_failures = sum(
    r["error"] is None and r["predicted_label"] is None for r in results
)

null_outputs = [
    r for r in results if r["error"] is None and isup_value(r["prediction"]) is None
]

out_of_range = [
    r
    for r in null_outputs
    if r["predicted_label"] is not None and not (0 <= r["predicted_label"] <= 5)
]

print("n_total:", n_total)
print("n_errors (B2 hard failures):", n_errors)
print("n_extraction_failures (label None, error None):", n_extraction_failures)
print('n_isup_grade_null_outputs:', len(null_outputs))
print('n_null_outputs_out_of_range_labels:', len(out_of_range))
print('null_truth_distribution:', Counter(r["truth_label"] for r in null_outputs))

PY
```

To see how often B2 forces retries in PANDA:
```bash
rg -c "Failed to parse JSON: Extra data" results/panda_benchmark.log
```

## Fix Plan

### 1. Fix `_extract_panda_label()` (P0 / CRITICAL)

```python
# In src/giant/eval/answer_extraction.py

def _extract_panda_label(text: str) -> int | None:
    """Extract ISUP grade from PANDA JSON response.

    Handles:
    - {"isup_grade": 0-5} -> returns integer (validated to 0..5)
    - {"isup_grade": null} -> returns 0 (benign/no cancer)
    - missing "isup_grade" -> returns None (extraction failure)
    """
    json_str = _extract_json_object(text)
    obj = json.loads(json_str)
    if not isinstance(obj, dict):
        return None
    if "isup_grade" not in obj:
        return None
    grade = obj["isup_grade"]
    if grade is None:
        return 0  # Benign/no cancer = ISUP Grade 0
    try:
        grade_int = int(grade)
    except (TypeError, ValueError):
        return None
    return grade_int if 0 <= grade_int <= 5 else None


# In extract_label(..., benchmark_name="panda"):
try:
    label = _extract_panda_label(text)
    return ExtractedAnswer(label=label, raw=text)  # JSON present → no fallback
except json.JSONDecodeError:
    return ExtractedAnswer(label=None, raw=text)  # JSON present but invalid → no fallback
except ValueError:
    pass  # No JSON object → allow integer fallback
```

### 2. Fix OpenAI `"Extra data"` Parsing (P0 / CRITICAL)

```python
# In src/giant/llm/openai_client.py

Parse `output_text` with `json.JSONDecoder().raw_decode()` starting after leading whitespace, ignore trailing content, then validate against `StepResponse`.
```

### 3. Add Dry Run Requirement to Benchmarking (PROCESS)

Before running expensive benchmarks, always do a dry run:

```bash
# REQUIRED before full benchmark runs
uv run giant benchmark panda --max-items=5 -v

# Review cost per item before proceeding
# PANDA: $0.37/item = $73/197 items
# GTEx: $0.038/item = $7/191 items
```

## Testing

Add test cases (at minimum):

```python
# In tests/unit/eval/test_answer_extraction.py

def test_panda_null_isup_grade():
    """isup_grade: null should map to Grade 0 (benign)."""
    text = '{"primary_pattern": null, "isup_grade": null}'
    result = extract_label(text, benchmark_name="panda", options=None)
    assert result.label == 0

def test_panda_missing_isup_grade_is_failure():
    """Missing isup_grade should not be treated as benign."""
    text = '{"reasoning": "no key"}'
    result = extract_label(text, benchmark_name="panda", options=None)
    assert result.label is None

def test_panda_valid_isup_grade():
    """Normal isup_grade extraction."""
    text = '{"isup_grade": 3}'
    result = extract_label(text, benchmark_name="panda", options=None)
    assert result.label == 3
```

## Lessons Learned

1. **Always dry run expensive benchmarks:** We spent $73.38 on a buggy run. A $1.85 dry run (5 items) would have revealed the issue.

2. **Validate extraction logic against all answer formats:** The PANDA dataset has a `null` case that wasn't tested.

3. **Log parse retries prominently:** `"Extra data"` parse failures are frequent and currently trigger silent re-queries.

4. **Test with real model outputs:** Unit tests used synthetic data; real LLM outputs are messier.

## Related Files

- `src/giant/eval/answer_extraction.py` - Primary bug location
- `src/giant/llm/openai_client.py` - Secondary bug location
- `results/panda_giant_openai_gpt-5.2_results.json` - Benchmark results
- `results/panda_benchmark.log` - Full run log

## Cost Analysis

| Benchmark | Items | Reported Cost | Cost/Item | Hard Failures (B2) | Extraction Failures (B1) |
|-----------|-------|------|-----------|---------------------|
| GTEx | 191 | $7.21 | $0.038 | 6 (3.1%) | 0 |
| TCGA | 221 | $15.14 | $0.068 | 6 (2.7%) | 0 |
| PANDA | 197 | $73.38 | $0.37 | 6 (3.0%) | 47 (23.9%) |
| **Total** | **609** | **$95.73** | - | **18 (3.0%)** | **47 (7.7%)** |

**Important:** Reported costs are a lower bound because parse-failed calls (B2) do not accumulate `usage`/cost today.

PANDA is 10x more expensive per item because prostate grading requires more navigation steps to examine Gleason patterns at cellular resolution.

## Sign-Off

- [x] Fix `_extract_panda_label()` to map null -> 0 (without mapping missing key) ✅ FIXED
- [x] Add unit tests for null + missing-key PANDA cases ✅ 6 tests added
- [x] Fix OpenAI `"Extra data"` parsing in `OpenAIProvider` ✅ FIXED
- [ ] Re-run PANDA benchmark with fix (optional, ~$73)
- [ ] Update benchmark-results.md with corrected analysis
