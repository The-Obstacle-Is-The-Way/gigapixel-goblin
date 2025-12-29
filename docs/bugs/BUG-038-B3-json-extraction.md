# BUG-038-B3: Naive Brace-Matching JSON Extraction

**Status**: CONFIRMED (not yet fixed)
**Severity**: HIGH
**Component**: `src/giant/eval/answer_extraction.py`
**Lines**: 151-167
**Discovered**: 2025-12-29
**Audit**: Comprehensive E2E Bug Audit (8 parallel swarm agents)
**Parent Ticket**: BUG-038

---

## Summary

The `_extract_json_object()` helper uses naive brace-matching (`find("{")` + `rfind("}")`) to extract JSON from text. This can span multiple JSON objects when the LLM outputs text containing more than one JSON structure, producing invalid JSON that fails to parse.

---

## Current Buggy Code

**File**: `src/giant/eval/answer_extraction.py:151-167`

```python
def _extract_json_object(text: str) -> str:
    """Extract the outermost JSON object from text.

    Args:
        text: Text potentially containing a JSON object.

    Returns:
        The extracted JSON string.

    Raises:
        ValueError: If no JSON object is found.
    """
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found")
    return text[start : end + 1]
```

---

## Problem Analysis

### Root Cause

`str.rfind("}")` finds the **last** occurrence of `}` in the entire string, not the **matching closing brace** for the first `{`. When multiple JSON objects exist in the output, this captures everything between the first `{` and last `}`, which is invalid JSON.

### Failure Scenarios

#### Scenario 1: Multiple JSON Objects (Most Common)

**Input**:
```text
Here's my reasoning: {"step": 1} and action: {"action_type": "crop", "x": 100}
```

**Current Behavior**:
- `find("{")` → index of first `{` (in `{"step": 1}`)
- `rfind("}")` → index of last `}` (in `{"action_type": "crop", "x": 100}`)
- Returns: `{"step": 1} and action: {"action_type": "crop", "x": 100}`
- `json.loads()` fails: **Invalid JSON**

**Expected Behavior**:
- Returns: `{"step": 1}` (first complete JSON object)
- `json.loads()` succeeds

#### Scenario 2: JSON Array Before Object

**Input**:
```text
Options: [1, 2, 3] Result: {"isup_grade": 2}
```

**Current Behavior**:
- `find("{")` → index of `{` in `{"isup_grade": 2}`
- `rfind("}")` → same `}`
- Returns: `{"isup_grade": 2}`
- **Works correctly** (by accident)

#### Scenario 3: Nested JSON (Works)

**Input**:
```text
{"outer": {"inner": 1, "nested": {"deep": 2}}}
```

**Current Behavior**:
- Returns entire string
- **Works correctly** (`rfind` happens to find the matching brace)

---

## Impact Assessment

### Direct Impact

- **Affected Component**: PANDA answer extraction
- **Caller**: `_extract_panda_label()` calls this function (currently the only call site)
- **Observed Frequency**: Not observed in saved benchmark artifacts; plausible when an LLM emits multiple JSON objects in one response

### Risk Level

- **LOW-MEDIUM**: Not observed in current benchmark runs, but possible failure mode
- **Covered by B1 fix**: The B1 fix for PANDA extraction prevents integer fallback when JSON is present but malformed, so this would result in `label=None` rather than an incorrect label

---

## Fix Implementation

### Option A: Decoder-Based Extraction (Recommended)

Uses `json.JSONDecoder().raw_decode()` to parse the first complete JSON value starting from the first `{`.

```python
import json

def _extract_json_object(text: str) -> str:
    """Extract the first valid JSON object from text.

    Uses json.JSONDecoder().raw_decode() to find the first complete
    JSON object, ignoring any text before or after it.

    Args:
        text: Text potentially containing a JSON object.

    Returns:
        The extracted JSON string (reserialized for validity).

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
        obj, _ = decoder.raw_decode(text, idx=start)
        if not isinstance(obj, dict):
            raise ValueError("Extracted JSON is not an object")
        # Reserialize to ensure valid JSON string
        return json.dumps(obj)
    except json.JSONDecodeError as e:
        raise ValueError(f"No valid JSON object found: {e}") from e
```

### Why This Works

1. `raw_decode(text, idx=start)` parses starting at position `start`
2. Returns `(obj, end_idx)` where `obj` is the parsed Python object
3. Ignores any text after the JSON object (no need to find closing brace)
4. `json.dumps(obj)` reserializes to ensure output is valid JSON

### Performance Note

- `json.dumps()` adds minimal overhead (< 1ms for typical PANDA responses)
- Could return `text[start:start+end_idx]` but reserialization is safer

---

## Test Cases

**File**: `tests/unit/eval/test_answer_extraction.py`

```python
import json
import pytest

from giant.eval.answer_extraction import _extract_json_object


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
        """Multiple JSON objects: returns first valid object (BUG-038-B3)."""
        text = 'Reasoning: {"step": 1} Action: {"action_type": "crop"}'
        result = _extract_json_object(text)
        # Should return first object, not span both
        assert json.loads(result) == {"step": 1}

    def test_nested_json_object(self) -> None:
        """Nested JSON object extracts correctly."""
        text = '{"outer": {"inner": 1}}'
        result = _extract_json_object(text)
        assert json.loads(result) == {"outer": {"inner": 1}}

    def test_deeply_nested_json_object(self) -> None:
        """Deeply nested JSON extracts correctly."""
        text = '{"a": {"b": {"c": {"d": 1}}}}'
        result = _extract_json_object(text)
        assert json.loads(result) == {"a": {"b": {"c": {"d": 1}}}}

    def test_json_in_markdown_code_fence(self) -> None:
        """JSON inside a Markdown code fence extracts correctly."""
        text = '```json\n{"key": "value"}\n```'
        result = _extract_json_object(text)
        assert json.loads(result) == {"key": "value"}

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

    def test_panda_style_response(self) -> None:
        """PANDA-style response with isup_grade extracts correctly."""
        text = '{"primary_pattern": null, "secondary_pattern": null, "isup_grade": 3}'
        result = _extract_json_object(text)
        parsed = json.loads(result)
        assert parsed["isup_grade"] == 3

    def test_malformed_json_raises_value_error(self) -> None:
        """Malformed JSON raises ValueError."""
        text = '{"key": value}'  # Missing quotes around value
        with pytest.raises(ValueError, match="No valid JSON object found"):
            _extract_json_object(text)
```

---

## Verification Steps

### 1. Write Failing Test First (TDD)

```bash
# Run test to confirm current implementation fails on multi-object case
uv run pytest tests/unit/eval/test_answer_extraction.py::TestExtractJsonObject::test_multiple_json_objects_returns_first -v
# Expected: FAIL (current implementation returns invalid JSON spanning both objects)
```

### 2. Apply Fix

Edit `src/giant/eval/answer_extraction.py:151-167` with the fix above.

### 3. Verify Fix

```bash
# Run all extraction tests
uv run pytest tests/unit/eval/test_answer_extraction.py -v

# Run full test suite
uv run pytest tests/unit -x

# Type check
uv run mypy src/giant

# Lint
uv run ruff check .
```

---

## Dependencies

- **Blocked by**: None
- **Blocks**: None
- **Related**: B2 (uses same `raw_decode` pattern in `openai_client.py`)

---

## Sign-Off Checklist

- [ ] Failing test written for `test_multiple_json_objects_returns_first`
- [ ] Fix applied to `_extract_json_object()`
- [ ] All 12 test cases pass
- [ ] Full test suite passes (`uv run pytest tests/unit`)
- [ ] Type check passes (`uv run mypy src/giant`)
- [ ] Lint passes (`uv run ruff check .`)
- [ ] PR created and merged
