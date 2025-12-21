# BUG-027: CSV Options Parsed as Single-Element List (Python vs JSON)

## Severity: P1 (High - causes 88% extraction failures)

## Status: Fixed

## Description

When running the TCGA benchmark, answer extraction fails for 22 out of 25 questions (88%). The root cause is that `MultiPathQA.csv` stores options as **Python list literals** (single quotes), but the loader attempts `json.loads()` (double quotes required), which fails silently and the fallback produces incorrect data.

---

## Evidence

### Benchmark Results (2025-12-20)

```
Results: n_total: 25, n_extraction_failures: 22
```

Only 3/25 answers were correctly extracted, leading to a meaningless 2.1% accuracy.

### Root Cause Demonstration

```python
options_str = "['Glioblastoma multiforme', 'Ovarian', ...]"

# What the code does:
json.loads(options_str)  # FAILS - single quotes not valid JSON
options_str.split("|")   # Returns: ["['Glioblastoma...']"] (1 element!)

# What it should do:
ast.literal_eval(options_str)  # Returns: ['Glioblastoma', 'Ovarian', ...] (30 elements)
```

### Resulting Prompt

**Actual (broken):**
```
Select from the following options:
1. ['Glioblastoma multiforme', 'Ovarian serous cystadenocarcinoma', ...]
```

**Expected (correct):**
```
Select from the following options:
1. Glioblastoma multiforme
2. Ovarian serous cystadenocarcinoma
...
30. Thymoma
```

### Model Behavior

The model interprets `1. [list of 30 items]` as a single option containing a Python list, then outputs an index into that list (e.g., `{"answer": 19}`). The answer extraction fails because 19 > 1 (apparent option count).

---

## Affected Code

`src/giant/eval/runner.py` (pre-fix):

```python
# Parse options if present
options = None
options_str = row.get("options", "")
if options_str:
    try:
        options = json.loads(options_str)  # FAILS for Python literals
    except json.JSONDecodeError:
        # Try splitting by common delimiters
        options = [o.strip() for o in options_str.split("|")]  # WRONG FALLBACK
```

---

## Affected Benchmarks

Pre-fix behavior:

| Benchmark | Options Format | Current Behavior | Status |
|-----------|----------------|------------------|--------|
| tcga | Python list `['a', 'b']` | 1-element list | **BROKEN (pre-fix)** |
| gtex | Python list `['a', 'b']` | 1-element list | **BROKEN (pre-fix)** |
| tcga_slidebench | Python list `['2', '3']` | 1-element list | **BROKEN (pre-fix)** |
| tcga_expert_vqa | Python list `['Low', 'High']` | 1-element list | **BROKEN (pre-fix)** |
| panda | Empty | N/A (no options) | OK |

---

## Proposed Fix

Add `ast.literal_eval` as secondary fallback in `src/giant/eval/runner.py`:

```python
import ast

# Parse options if present
options = None
options_str = row.get("options", "")
if options_str:
    # Try JSON first (double quotes)
    try:
        options = json.loads(options_str)
    except json.JSONDecodeError:
        # Try Python literal (single quotes)
        try:
            options = ast.literal_eval(options_str)
        except (ValueError, SyntaxError):
            # Last resort: pipe-delimited
            options = [o.strip() for o in options_str.split("|")]
```

---

## Impact Assessment

| Metric | Before Fix | After Fix |
|--------|------------|-----------|
| Extraction failures (TCGA) | 88% | ~0% |
| Extraction failures (all benchmarks) | Unknown | ~0% |
| Cost wasted on failed benchmark | $0.99 | $0 |

---

## Testing Checklist

- [x] Add unit test: `test_options_parsing_python_literal()`
- [x] Add unit test: `test_options_parsing_json()`
- [x] Add unit test: `test_options_parsing_pipe_delimited()`
- [ ] Verify all benchmarks load with correct option counts
- [ ] Re-run TCGA benchmark and confirm extraction rate improves

---

## Resolution

Fixed by parsing `options` using JSON first, then Python literal lists, and failing loudly
on unparseable formats (instead of silently producing a 1-element list). Also updated prompt
construction to always show options to the model when options exist.

- Code: `src/giant/eval/runner.py` (`BenchmarkRunner._parse_options`, `BenchmarkRunner._inject_options`)
- Tests: `tests/unit/eval/test_runner.py` (`test_parses_python_literal_options`)

---

## References

- Failed benchmark run: `results/openai-benchmark-20251220-210900/`
- CSV data: `data/multipathqa/MultiPathQA.csv`
- Loader: `src/giant/eval/runner.py`
