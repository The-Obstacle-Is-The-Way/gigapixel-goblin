# BUG-038: Comprehensive E2E Bug Audit

**Status**: COMPLETED - ALL BUGS FIXED (B1, B2, B3, B4, B5, B7, B8, B9, B10, B11, B12)
**Severity**: MIXED (see table below)
**Audit Date**: 2025-12-29
**Fix Date**: 2025-12-30
**Audited By**: 8 parallel swarm agents
**Cost Impact**: Reported $73.38 spent on PANDA benchmark run (lower bound; see Cost Notes)

---

## Individual Bug Specifications

Each bug has a dedicated spec document with implementation-ready details:

| Bug | Severity | Spec Document |
|-----|----------|---------------|
| B1, B2 | CRITICAL | [../archive/bugs/BUG-038-panda-answer-extraction.md](../archive/bugs/BUG-038-panda-answer-extraction.md) (**FIXED** ✅ ARCHIVED) |
| B3 | HIGH | [../archive/bugs/BUG-038-B3-json-extraction.md](../archive/bugs/BUG-038-B3-json-extraction.md) (**FIXED** ✅ ARCHIVED) |
| B4 | HIGH | [../archive/bugs/BUG-038-B4-anthropic-json-parsing.md](../archive/bugs/BUG-038-B4-anthropic-json-parsing.md) (**FIXED** ✅ ARCHIVED) |
| B5 | HIGH | [../archive/bugs/BUG-038-B5-token-count-none.md](../archive/bugs/BUG-038-B5-token-count-none.md) (**FIXED** ✅ ARCHIVED) |
| B7 | MEDIUM | [../archive/bugs/BUG-038-B7-retry-counter-logic.md](../archive/bugs/BUG-038-B7-retry-counter-logic.md) (**FIXED** ✅ ARCHIVED) |
| B8 | MEDIUM | [../archive/bugs/BUG-038-B8-empty-base64.md](../archive/bugs/BUG-038-B8-empty-base64.md) (**FIXED** ✅ ARCHIVED) |
| B9 | MEDIUM | [../archive/bugs/BUG-038-B9-recursive-retry.md](../archive/bugs/BUG-038-B9-recursive-retry.md) (**FIXED** ✅ ARCHIVED) |
| B10 | MEDIUM | [../archive/bugs/BUG-038-B10-unknown-action-type.md](../archive/bugs/BUG-038-B10-unknown-action-type.md) (**FIXED** ✅ ARCHIVED) |
| B11 | LOW | [../archive/bugs/BUG-038-B11-comment-fix.md](../archive/bugs/BUG-038-B11-comment-fix.md) (**FIXED** ✅ ARCHIVED) |
| B12 | LOW | [../archive/bugs/BUG-038-B12-empty-message-content.md](../archive/bugs/BUG-038-B12-empty-message-content.md) (**FIXED** ✅ ARCHIVED) |

Each spec includes:
- Current buggy code
- Root cause analysis
- Fix implementation (copy-paste ready)
- Test cases
- Verification steps
- Sign-off checklist

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
- In the pre-fix benchmark artifacts, PANDA reports **9.4% balanced accuracy** largely because `"isup_grade": null` was not mapped to benign label 0; rescoring the saved predictions with the fixed extractor (no new LLM calls) yields **19.7% ± 1.9% balanced accuracy** (bootstrap mean ± std; point estimate 19.75%) with **0 extraction failures** (that rescore still includes the 6 B2 hard failures).
- In the pre-fix benchmark artifacts, OpenAI `"Extra data"` parse failures blocked **18/609 items (3.0%)** across all benchmarks and triggered frequent retries; this also **undercounted spend** because parse-failed calls did not accumulate `usage` (fixed by B2).

---

## Finding Summary Table

| ID | Location | Severity | Status | Spec Doc | Description |
|----|----------|----------|--------|----------|-------------|
| **B1** | `src/giant/eval/answer_extraction.py:45-74` | CRITICAL | **FIXED** | [../archive/bugs/BUG-038-panda-answer-extraction.md](../archive/bugs/BUG-038-panda-answer-extraction.md) | PANDA `"isup_grade": null` maps to label 0 (benign); any JSON present but missing/invalid/out-of-range returns `None` without integer fallback |
| **B2** | `src/giant/llm/openai_client.py:245` | CRITICAL | **FIXED** | [../archive/bugs/BUG-038-panda-answer-extraction.md](../archive/bugs/BUG-038-panda-answer-extraction.md) | Uses `json.JSONDecoder().raw_decode()` (skipping leading whitespace) to ignore trailing text after JSON |
| **B3** | `src/giant/eval/answer_extraction.py:151-180` | HIGH | **FIXED** | [../archive/bugs/BUG-038-B3-json-extraction.md](../archive/bugs/BUG-038-B3-json-extraction.md) | Uses `json.JSONDecoder().raw_decode()` to extract the first complete JSON object (no naive brace matching) |
| **B4** | `src/giant/llm/anthropic_client.py:73-113` | HIGH | **FIXED** | [../archive/bugs/BUG-038-B4-anthropic-json-parsing.md](../archive/bugs/BUG-038-B4-anthropic-json-parsing.md) | Raises clear `LLMParseError` when `tool_input["action"]` is a string containing invalid JSON |
| **B5** | `src/giant/llm/openai_client.py:275-295`, `src/giant/llm/anthropic_client.py:246-266` | HIGH | **FIXED** | [../archive/bugs/BUG-038-B5-token-count-none.md](../archive/bugs/BUG-038-B5-token-count-none.md) | Guard against `usage.*_tokens is None` to avoid TypeError-driven `LLMError` and improve root-cause clarity |
| **B6** | `src/giant/agent/context.py:159` | — | RETRACTED | N/A | Step guard is correct and unit-tested; no off-by-one bug found |
| **B7** | `src/giant/agent/runner.py:439-456` | MEDIUM | **FIXED** | [../archive/bugs/BUG-038-B7-retry-counter-logic.md](../archive/bugs/BUG-038-B7-retry-counter-logic.md) | Resets `_consecutive_errors` after successful invalid-region recovery (crop or answer); regression test added |
| **B8** | `src/giant/llm/converters.py:260-269` | MEDIUM | **FIXED** | [../archive/bugs/BUG-038-B8-empty-base64.md](../archive/bugs/BUG-038-B8-empty-base64.md) | Empty base64 (`""`) decodes to zero bytes and fails later in `Image.open()` |
| **B9** | `src/giant/agent/runner.py:385-502` | MEDIUM | **FIXED** | [../archive/bugs/BUG-038-B9-recursive-retry.md](../archive/bugs/BUG-038-B9-recursive-retry.md) | Refactored recursive invalid-region retry to iterative loop for cleaner control flow |
| **B10** | `src/giant/llm/openai_client.py:72-117` | MEDIUM | **FIXED** | [../archive/bugs/BUG-038-B10-unknown-action-type.md](../archive/bugs/BUG-038-B10-unknown-action-type.md) | Raises clear `LLMParseError` on unknown `action_type` (avoids confusing pydantic discriminator errors) |
| **B11** | `src/giant/agent/context.py:268` | LOW | **FIXED** | [../archive/bugs/BUG-038-B11-comment-fix.md](../archive/bugs/BUG-038-B11-comment-fix.md) | Comment clarity on user-message index vs LLM step numbering |
| **B12** | `src/giant/llm/protocol.py:129-137` | LOW | **FIXED** | [../archive/bugs/BUG-038-B12-empty-message-content.md](../archive/bugs/BUG-038-B12-empty-message-content.md) | Add `min_length=1` for `Message.content` to prevent empty API payloads |

---

## CRITICAL BUGS

### B1: PANDA `isup_grade: null` Not Mapped to Grade 0 (FIXED)

**Location (fixed)**: `src/giant/eval/answer_extraction.py:45-148`

**Status**: FIXED (2025-12-29)

**Problem (pre-fix)**: When the model indicates benign/no cancer, PANDA predictions frequently include `{"isup_grade": null}`. The pre-fix extractor raised a `TypeError` on `int(None)`, returned `None`, and then `extract_label()` fell back to naive integer parsing (often grabbing coordinate numbers), producing out-of-range or incorrect labels.

**Pre-fix code (for reference)**:
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
- Rescore-only with fixed extractor (no new LLM calls): **19.7% ± 1.9% balanced accuracy** (point estimate 19.75%), **28.4% raw accuracy** (56/197 correct; still includes 6 B2 failures)

**Fix (must distinguish null vs missing key, and avoid integer fallback when JSON is present):**
```python
# In _extract_panda_label(text):
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

---

### B2: JSON "Extra Data" Error on Trailing LLM Text (FIXED)

**Location**: `src/giant/llm/openai_client.py:245`

**Status**: FIXED (2025-12-29)

**Problem (pre-fix)**: LLM sometimes outputs explanatory text after a JSON object:
```text
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

**Fix (implemented; avoids brace matching):**
- Parse the first JSON value from `output_text` using `json.JSONDecoder().raw_decode()` starting after leading whitespace (ignore trailing content).
- Validate against `StepResponse`; raise `LLMParseError` on `JSONDecodeError` / `ValidationError`.

---

## HIGH SEVERITY BUGS

### B3: Naive Brace-Matching JSON Extraction

**Location (fixed)**: `src/giant/eval/answer_extraction.py:151-180`

**Status**: FIXED (2025-12-29; commit `733bda5a`)

**Problem**: Uses `find("{")` + `rfind("}")` which can span multiple JSON objects, producing invalid JSON that causes `json.loads()` to fail.

**Pre-fix code (for reference; commit `e7172a32`)**:
```python
def _extract_json_object(text: str) -> str:
    """Extract the outermost JSON object from text."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found")
    return text[start : end + 1]
```

**Failure Scenarios**:

1. **Multiple JSON objects** (most common):
```text
Here's my reasoning: {"step": 1} and action: {"action_type": "crop", "x": 100}
```
Current: Returns `{"step": 1} and action: {"action_type": "crop", "x": 100}` → invalid JSON
Expected: Returns `{"step": 1}` (first valid object)

2. **JSON with trailing text** (already handled by B2 in openai_client, but not here):
```text
{"isup_grade": 3} I hope this helps!
```
Current: Works (rfind finds the right `}`)
Expected: Same (works)

3. **Nested JSON** (edge case):
```text
{"outer": {"inner": 1}}
```
Current: Works (rfind finds the right `}`)
Expected: Same (works)

**Caller Analysis**: Pre-fix, called from `_extract_panda_label()`; current code also uses it in `_has_isup_grade_key()`.

**Fix** (use `json.JSONDecoder().raw_decode()`):
```python
def _extract_json_object(text: str) -> str:
    """Extract the first valid JSON object from text.

    Uses json.JSONDecoder().raw_decode() to find the first complete
    JSON object, ignoring any text before or after it.

    Args:
        text: Text potentially containing a JSON object.

    Returns:
        The extracted JSON string.

    Raises:
        ValueError: If no valid JSON object is found.
    """
    # Find first '{' to start scanning
    start = text.find("{")
    if start == -1:
        raise ValueError("No JSON object found")

    # Use raw_decode to parse the first complete JSON object
    decoder = json.JSONDecoder()
    try:
        obj, end_idx = decoder.raw_decode(text, idx=start)
        if not isinstance(obj, dict):
            raise ValueError("Extracted JSON is not an object")
        return json.dumps(obj)
    except json.JSONDecodeError as e:
        raise ValueError(f"No valid JSON object found: {e}") from e
```

**Alternative Fix** (simpler, reserialize):
```python
def _extract_json_object(text: str) -> str:
    """Extract the first valid JSON object from text."""
    start = text.find("{")
    if start == -1:
        raise ValueError("No JSON object found")

    decoder = json.JSONDecoder()
    try:
        obj, _ = decoder.raw_decode(text, idx=start)
        if not isinstance(obj, dict):
            raise ValueError("Extracted JSON is not an object")
        return json.dumps(obj)  # Reserialize to ensure valid JSON string
    except json.JSONDecodeError as e:
        raise ValueError(f"No valid JSON object found: {e}") from e
```

**Test Cases** (add to `tests/unit/eval/test_answer_extraction.py`):
```python
class TestExtractJsonObject:
    """Tests for _extract_json_object helper."""

    def test_single_json_object(self) -> None:
        """Single JSON object extracts correctly."""
        text = '{"key": "value"}'
        result = _extract_json_object(text)
        assert json.loads(result) == {"key": "value"}

    def test_json_with_leading_text(self) -> None:
        """JSON with leading text extracts correctly."""
        text = 'Here is my response: {"key": "value"}'
        result = _extract_json_object(text)
        assert json.loads(result) == {"key": "value"}

    def test_json_with_trailing_text(self) -> None:
        """JSON with trailing text extracts correctly."""
        text = '{"key": "value"} I hope this helps!'
        result = _extract_json_object(text)
        assert json.loads(result) == {"key": "value"}

    def test_multiple_json_objects_returns_first(self) -> None:
        """Multiple JSON objects: returns first valid object."""
        text = 'Reasoning: {"step": 1} Action: {"action_type": "crop"}'
        result = _extract_json_object(text)
        assert json.loads(result) == {"step": 1}

    def test_nested_json_object(self) -> None:
        """Nested JSON object extracts correctly."""
        text = '{"outer": {"inner": 1}}'
        result = _extract_json_object(text)
        assert json.loads(result) == {"outer": {"inner": 1}}

    def test_no_json_raises_value_error(self) -> None:
        """No JSON object raises ValueError."""
        text = "No JSON here, just plain text"
        with pytest.raises(ValueError, match="No JSON object found"):
            _extract_json_object(text)

    def test_empty_string_raises_value_error(self) -> None:
        """Empty string raises ValueError."""
        with pytest.raises(ValueError, match="No JSON object found"):
            _extract_json_object("")

    def test_json_array_raises_value_error(self) -> None:
        """JSON array (not object) raises ValueError."""
        text = '[1, 2, 3]'
        with pytest.raises(ValueError, match="No JSON object found"):
            _extract_json_object(text)
```

**Impact**: LOW (only affects PANDA extraction, and only when LLM outputs multiple JSON objects in the same response, which is rare but possible).

---

### B4: Silent JSON Parsing Failure in Anthropic Client

**Location (fixed)**: `src/giant/llm/anthropic_client.py:73-113`

**Status**: FIXED (2025-12-29; commit `733bda5a`)

**Problem (pre-fix)**: If Anthropic returns `tool_input["action"]` as a string, invalid JSON was caught and ignored. The subsequent pydantic error was still raised, but the root-cause (“action was a string but not valid JSON”) was not explicit.

**Pre-fix code (for reference; commit `e7172a32`)**:
```python
except json.JSONDecodeError:
    pass  # Let pydantic handle the validation error
```

**Spec doc**: [../archive/bugs/BUG-038-B4-anthropic-json-parsing.md](../archive/bugs/BUG-038-B4-anthropic-json-parsing.md)

---

### B5: Defensive Guard for None Token Counts

**Location (fixed)**: `src/giant/llm/openai_client.py:275-295` and `src/giant/llm/anthropic_client.py:246-266`

**Status**: FIXED (2025-12-29; commit `f1741576`)

**Problem (pre-fix)**: Token counts from SDK could theoretically be `None`. This triggered a `TypeError` during `total_tokens` computation which then became a generic `LLMError` via the catch-all handler.
```python
prompt_tokens = usage.input_tokens
completion_tokens = usage.output_tokens
total_tokens = prompt_tokens + completion_tokens  # TypeError if None
```

**Spec doc**: [../archive/bugs/BUG-038-B5-token-count-none.md](../archive/bugs/BUG-038-B5-token-count-none.md)

---

## MEDIUM SEVERITY BUGS

### B6: Off-by-One in Step Guard (RETRACTED)

**Location**: `src/giant/agent/context.py:159`

**Result**: Not a bug. The guard is correct and prevents the context builder from emitting a user message for a step beyond `max_steps`.

**Why the current code is correct**:

- `ContextManager.get_messages()` iterates over *completed turns* and builds the prompt for the *next* LLM call.
- After adding the assistant message for the current step, it must decide whether it is allowed to append the next-step user message (with the crop image).
- The correct condition is `if step >= self.max_steps: break`, because when `step == max_steps` you have already consumed the final allowed step and must not construct a step `max_steps + 1` user prompt.

**Evidence**:

- Code: `src/giant/agent/context.py:159` uses `>=` (prevent step `max_steps + 1`).
- `PromptBuilder` explicitly rejects `step > max_steps` (`src/giant/prompts/builder.py:82-83`), and this guard prevents hitting that path.
- Unit tests cover prompt structure and step accounting, including final-step semantics:
  - `tests/unit/agent/test_context.py`
  - `tests/unit/agent/test_runner.py::TestGIANTAgentLoopLimit::test_crop_at_max_steps_ignored`

---

### B7: Retry Counter Semantics Leak After Recovery

**Location (fixed)**: `src/giant/agent/runner.py:439-456`

**Status**: FIXED (2025-12-29; commit `f9465368`)

**Problem (pre-fix)**: After a successful invalid-region recovery crop, `_consecutive_errors` was not reset to 0, so a recovered failure could leak into subsequent steps.

**Fix**: Reset `_consecutive_errors` to 0 after a successful recovery crop or answer, and add a regression test.

**Spec doc**: [../archive/bugs/BUG-038-B7-retry-counter-logic.md](../archive/bugs/BUG-038-B7-retry-counter-logic.md)

---

### B8: Empty Base64 Not Caught Early

**Location (fixed)**: `src/giant/llm/converters.py:260-269`

**Status**: FIXED (2025-12-29; commit `85d9e074`)

**Problem (pre-fix)**: After None check, empty string `""` decoded successfully but produced zero bytes, failing later in `Image.open()`.

**Spec doc**: [../archive/bugs/BUG-038-B8-empty-base64.md](../archive/bugs/BUG-038-B8-empty-base64.md)

---

### B9: Recursive Retry Handling (FIXED)

**Location (fixed)**: `src/giant/agent/runner.py:385-502`

**Status**: FIXED (2025-12-30)

**Problem (pre-fix)**: Used recursion via `await self._handle_crop()` within `_handle_invalid_region()`. While bounded by `max_retries=3`, recursion is harder to trace and debug than iteration.

**Fix**: Refactored `_handle_invalid_region()` to use an iterative `while True` loop that:
1. Increments error counter and checks max retries
2. Asks LLM for corrected coordinates
3. Validates and executes crop inline (no recursion)
4. Continues loop on validation/execution failure
5. Returns on success (crop or answer) or max retries

**Spec doc**: [../archive/bugs/BUG-038-B9-recursive-retry.md](../archive/bugs/BUG-038-B9-recursive-retry.md)

---

### B10: Unknown Action Type Error Clarity

**Location (fixed)**: `src/giant/llm/openai_client.py:72-117`

**Status**: FIXED (2025-12-29; commit `733bda5a`)

**Problem (pre-fix)**: Unknown `action_type` was rejected by pydantic, but the discriminator error is confusing; raise a clearer `LLMParseError`.

**Spec doc**: [../archive/bugs/BUG-038-B10-unknown-action-type.md](../archive/bugs/BUG-038-B10-unknown-action-type.md)

---

## LOW SEVERITY ISSUES

### B11: Misleading Comment on Step Index

**Location (fixed)**: `src/giant/agent/context.py:268`

**Status**: FIXED (2025-12-29; commit `b5a57f59`)

Pre-fix, an inline comment implied `user_msg_index == step - 1` without clarifying which “step” was meant (LLM step numbering vs trajectory indexing). Cosmetic clarity issue only.

**Spec doc**: [../archive/bugs/BUG-038-B11-comment-fix.md](../archive/bugs/BUG-038-B11-comment-fix.md)

---

### B12: Empty Message.content Allowed (Defensive)

**Location (fixed)**: `src/giant/llm/protocol.py:129-137`

Pre-fix, the `Message` model allowed `content=[]` which can lead to provider API errors. This is now prevented via `min_length=1`.

**Status**: FIXED (2025-12-29; commit `3185b036`)

**Spec doc**: [../archive/bugs/BUG-038-B12-empty-message-content.md](../archive/bugs/BUG-038-B12-empty-message-content.md)

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

No known unit-test coverage gaps remain for the BUG-038 fixes. Each fixed item has either dedicated regression tests or is covered by existing runner tests (see the individual spec docs for exact pytest targets).

---

## FIX PRIORITY

### Completed
1. **B1**: PANDA `isup_grade: null` → 0 (benign) ✅
2. **B2**: OpenAI `"Extra data"` parsing (ignore trailing text) ✅
3. **B3**: Replace brace matching with decoder-based JSON extraction ✅
4. **B4**: Make Anthropic stringified-`action` decode errors explicit ✅
5. **B10**: Unknown `action_type` clearer error ✅
6. **B5**: Defensive guard for `usage.*_tokens is None` ✅
7. **B8**: Empty base64 early validation in `count_image_pixels_in_messages()` ✅
8. **B12**: `Message.content` `min_length=1` ✅
9. Added/updated unit tests for fixed bugs ✅

### All Code Fixes Complete
10. **B7**: Retry counter reset ✅
11. **B11**: Comment clarity ✅
12. **B9**: Iterative retry refactor ✅

---

## Sign-Off Checklist

- [x] **B1**: Fix `_extract_panda_label()` null → 0 (missing key remains failure) ✅ FIXED 2025-12-29
- [x] **B2**: Fix OpenAI `"Extra data"` parsing (ignore trailing text; validate `StepResponse`) ✅ FIXED 2025-12-29
- [x] **B3**: Replace brace matching with decoder-based JSON extraction ✅ FIXED 2025-12-29
- [x] **B4**: Make Anthropic invalid JSON-string root cause explicit ✅ FIXED 2025-12-29
- [x] **B5**: Guard against `usage.*_tokens is None` ✅ FIXED 2025-12-29
- [x] **B10**: Raise clear `LLMParseError` for unknown `action_type` ✅ FIXED 2025-12-29
- [x] Add unit tests for PANDA null + missing-key cases ✅ 6 tests added
- [x] Add unit tests for OpenAI trailing-text JSON ✅ 3 tests added
- [x] Add unit tests for B3/B4/B10 ✅ (12 + 3 + 7 tests)
- [x] Add unit tests for B5/B8/B12 ✅ (6 + 2 + 1 tests)
- [x] **B8**: Empty base64 early validation ✅ FIXED 2025-12-29
- [x] **B12**: Prevent `Message(content=[])` via `min_length=1` ✅ FIXED 2025-12-29
- [x] **B7**: Retry counter reset logic fixed and tested ✅ FIXED 2025-12-29
- [x] **B11**: Comment updated for clarity ✅ FIXED 2025-12-29
- [x] **B9**: Refactored recursive retry to iterative loop ✅ FIXED 2025-12-30
- [x] Re-score PANDA run after B1 fix (no new LLM calls) ✅ VERIFIED 19.7% ± 1.9% balanced accuracy (bootstrap mean ± std)
- [x] Update `docs/results/benchmark-results.md` with corrected PANDA analysis ✅

### Optional Follow-Ups (Cost / Data Required)

- Re-run PANDA benchmark with BUG-038 fixes applied (requires WSIs + live API spend; pre-fix baseline cost ~$73)
- Re-run GTEx/TCGA benchmarks with BUG-038-B2 fix applied to remove the 6 hard failures per benchmark and to get accurate cost accounting

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
