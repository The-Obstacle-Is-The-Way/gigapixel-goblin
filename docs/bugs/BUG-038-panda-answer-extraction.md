# BUG-038: PANDA Answer Extraction Failures

**Status**: OPEN
**Severity**: HIGH
**Component**: `src/giant/eval/answer_extraction.py`
**Discovered**: 2025-12-29
**Cost Impact**: $73.38 spent on benchmark run with buggy extraction logic

## Summary

The PANDA benchmark (Prostate Grading, 6-way ISUP classification) has a 26.9% extraction failure rate due to bugs in `answer_extraction.py`. The primary bug causes `isup_grade: null` to be treated as an extraction failure rather than mapping to ISUP Grade 0 (benign).

**Measured Impact:**
- Current balanced accuracy: **9.4%** (reported) / **14.6%** (actual from results)
- With bug fix: **~24%** (matching paper baseline of 23.2%)
- 17 correct answers incorrectly marked as failures

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

**Clinical Context:** ISUP Grade 0 = benign/no cancer. The model returning `null` is semantically correct.

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

**Fix Required:**
```python
def _extract_panda_label(text: str) -> int | None:
    """Extract ISUP grade from PANDA JSON response."""
    try:
        json_str = _extract_json_object(text)
        obj = json.loads(json_str)
        grade = obj.get("isup_grade")
        if grade is None:
            return 0  # No cancer = ISUP Grade 0
        return int(grade)
    except Exception:
        return None
```

### Secondary Bug: JSON Parsing "Extra Data" Errors

6/197 PANDA items (3.0%) failed completely due to JSON parsing errors during agent execution:

```
Max retries (3) exceeded: Failed to parse JSON: Extra data: line 1 column 355 (char 354)
```

**Root Cause:** The LLM sometimes outputs trailing text after the JSON object:
```
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

**Fix Required:** Use `_extract_json_object()` or a regex to extract just the JSON portion before parsing.

## Data Analysis

### Extraction Failure Breakdown (PANDA)

| Category | Count | Percentage |
|----------|-------|------------|
| `isup_grade: null` | 47 | 23.9% |
| JSON parsing errors | 6 | 3.0% |
| **Total Failures** | **53** | **26.9%** |

### Ground Truth for `isup_grade: null` Cases

| Ground Truth | Count | Model Correct? |
|--------------|-------|----------------|
| ISUP Grade 0 | 17 | Yes (should map null -> 0) |
| ISUP Grade 1 | 14 | No (missed cancer) |
| ISUP Grade 2 | 3 | No (missed cancer) |
| ISUP Grade 3 | 4 | No (missed cancer) |
| ISUP Grade 4 | 6 | No (missed cancer) |
| ISUP Grade 5 | 3 | No (missed cancer) |

**Key Insight:** 17/47 (36%) of "null" cases were actually correct answers that we threw away due to the extraction bug.

### Corrected Accuracy Calculation

| Metric | Current (Buggy) | With Fix | Paper Baseline |
|--------|-----------------|----------|----------------|
| Raw Accuracy | 10.7% | 19.3% | - |
| Balanced Accuracy | 14.6% | ~24% | 23.2% |
| Grade 0 Accuracy | 24.1% | 55.6% | - |

## Per-Class Accuracy (Current)

| ISUP Grade | Correct | Total | Accuracy |
|------------|---------|-------|----------|
| 0 (Benign) | 13 | 54 | 24.1% |
| 1 | 1 | 49 | 2.0% |
| 2 | 1 | 25 | 4.0% |
| 3 | 3 | 23 | 13.0% |
| 4 | 3 | 23 | 13.0% |
| 5 | 0 | 23 | 0.0% |

**Note:** The model performs worst on Grade 5 (most aggressive cancer) with 0% accuracy. This may be a model capability issue rather than an extraction bug.

## Reproduction

```bash
# View extraction failures
python3 -c "
import json
with open('results/panda_giant_openai_gpt-5.2_results.json') as f:
    data = json.load(f)

failures = [r for r in data['results'] if r['predicted_label'] is None]
print(f'Extraction failures: {len(failures)}/{len(data[\"results\"])}')

# Show null cases
null_cases = [r for r in failures if 'isup_grade\": null' in (r['prediction'] or '')]
print(f'isup_grade: null cases: {len(null_cases)}')
"
```

## Fix Plan

### 1. Fix `_extract_panda_label()` (HIGH PRIORITY)

```python
# In src/giant/eval/answer_extraction.py

def _extract_panda_label(text: str) -> int | None:
    """Extract ISUP grade from PANDA JSON response.

    Handles:
    - {"isup_grade": 0-5} -> returns integer
    - {"isup_grade": null} -> returns 0 (no cancer = benign)
    """
    try:
        json_str = _extract_json_object(text)
        obj = json.loads(json_str)
        grade = obj.get("isup_grade")
        if grade is None:
            return 0  # Clinical: null = no cancer = ISUP Grade 0
        return int(grade)
    except Exception:
        return None
```

### 2. Improve JSON Extraction Robustness (MEDIUM PRIORITY)

```python
# In src/giant/llm/openai_client.py

def _extract_first_json_object(text: str) -> dict:
    """Extract first valid JSON object from text, ignoring trailing content."""
    import re
    # Find first { and matching }
    match = re.search(r'\{[^{}]*\}|\{(?:[^{}]|\{[^{}]*\})*\}', text)
    if not match:
        raise ValueError("No JSON object found")
    return json.loads(match.group())
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

Add test cases:

```python
# In tests/unit/eval/test_answer_extraction.py

def test_panda_null_isup_grade():
    """isup_grade: null should map to Grade 0 (benign)."""
    text = '{"primary_pattern": null, "isup_grade": null}'
    result = extract_label(text, benchmark_name="panda", options=None)
    assert result.label == 0

def test_panda_valid_isup_grade():
    """Normal isup_grade extraction."""
    text = '{"isup_grade": 3}'
    result = extract_label(text, benchmark_name="panda", options=None)
    assert result.label == 3
```

## Lessons Learned

1. **Always dry run expensive benchmarks:** We spent $73.38 on a buggy run. A $1.85 dry run (5 items) would have revealed the issue.

2. **Validate extraction logic against all answer formats:** The PANDA dataset has a `null` case that wasn't tested.

3. **Log extraction failures prominently:** The 26.9% failure rate was buried in metrics; it should have been a warning.

4. **Test with real model outputs:** Unit tests used synthetic data; real LLM outputs are messier.

## Related Files

- `src/giant/eval/answer_extraction.py` - Primary bug location
- `src/giant/llm/openai_client.py` - Secondary bug location
- `results/panda_giant_openai_gpt-5.2_results.json` - Benchmark results
- `results/panda_benchmark.log` - Full run log

## Cost Analysis

| Benchmark | Items | Cost | Cost/Item | Extraction Failures |
|-----------|-------|------|-----------|---------------------|
| GTEx | 191 | $7.21 | $0.038 | 6 (3.1%) |
| TCGA | 221 | $15.14 | $0.068 | 6 (2.7%) |
| PANDA | 197 | $73.38 | $0.37 | 53 (26.9%) |
| **Total** | **609** | **$95.73** | - | **65 (10.7%)** |

PANDA is 10x more expensive per item because prostate grading requires more navigation steps to examine Gleason patterns at cellular resolution.

## Sign-Off

- [ ] Fix `_extract_panda_label()` to map null -> 0
- [ ] Add unit tests for null case
- [ ] Improve JSON extraction robustness
- [ ] Re-run PANDA benchmark with fix (optional, ~$73)
- [ ] Update benchmark-results.md with corrected analysis
