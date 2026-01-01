# BUG-038-B4: Silent JSON Parsing Failure in Anthropic Client

**Status**: FIXED (2025-12-29)
**Severity**: HIGH
**Component**: `src/giant/llm/anthropic_client.py`
**Fixed In**: `733bda5a` (fix: BUG-038 B3, B4, B10 - JSON parsing robustness)
**Buggy Commit**: `e7172a32` (pre-fix on main)
**Current Lines (fixed)**: 73-113
**Buggy Lines (pre-fix)**: 73-106 (swallowed `JSONDecodeError` at 97-98)
**Discovered**: 2025-12-29
**Audit**: Comprehensive E2E Bug Audit (8 parallel swarm agents)
**Parent Ticket**: BUG-038

---

## Summary

When Anthropic returns `tool_input["action"]` as a JSON string instead of a parsed dict, the original implementation swallowed `JSONDecodeError` and let pydantic fail later with a confusing message that didn't indicate the root cause (malformed JSON string).

This is fixed in `733bda5a` by raising `LLMParseError` immediately with the underlying `JSONDecodeError` details.

---

## Original Buggy Code (pre-fix)

**File (pre-fix)**: `src/giant/llm/anthropic_client.py:73-106` (commit `e7172a32`)

```python
def _parse_tool_use_to_step_response(tool_input: dict[str, Any]) -> StepResponse:
    """Parse tool use input into StepResponse.

    Handles the case where Anthropic returns nested fields as JSON strings
    instead of parsed dicts (common with complex tool schemas).

    Args:
        tool_input: The input dictionary from the tool use.

    Returns:
        Parsed StepResponse.

    Raises:
        LLMParseError: If parsing fails.
    """
    try:
        # Handle case where 'action' is returned as a JSON string instead of dict
        # This can happen with complex nested schemas in tool use
        if isinstance(tool_input.get("action"), str):
            try:
                tool_input = {
                    **tool_input,
                    "action": json.loads(tool_input["action"]),
                }
            except json.JSONDecodeError:
                pass  # Let pydantic handle the validation error

        return StepResponse.model_validate(tool_input)
    except ValidationError as e:
        raise LLMParseError(
            f"Failed to parse StepResponse: {e}",
            raw_output=str(tool_input),
            provider="anthropic",
        ) from e
```

---

## Current Fixed Code

**File (current)**: `src/giant/llm/anthropic_client.py:73-113` (commit `733bda5a`)

```python
def _parse_tool_use_to_step_response(tool_input: dict[str, Any]) -> StepResponse:
    """Parse tool use input into StepResponse.

    Handles the case where Anthropic returns nested fields as JSON strings
    instead of parsed dicts (common with complex tool schemas).

    Args:
        tool_input: The input dictionary from the tool use.

    Returns:
        Parsed StepResponse.

    Raises:
        LLMParseError: If parsing fails.
    """
    try:
        # Handle case where 'action' is returned as a JSON string instead of dict.
        # If the string is invalid JSON, raise an LLMParseError that preserves the
        # real root cause (instead of swallowing JSONDecodeError).
        if isinstance(tool_input.get("action"), str):
            action_str = tool_input["action"]
            try:
                tool_input = {
                    **tool_input,
                    "action": json.loads(action_str),
                }
            except json.JSONDecodeError as e:
                raise LLMParseError(
                    "Anthropic tool_input.action was a string but was not "
                    f"valid JSON: {e}",
                    raw_output=str(tool_input),
                    provider="anthropic",
                ) from e

        return StepResponse.model_validate(tool_input)
    except ValidationError as e:
        raise LLMParseError(
            f"Failed to parse StepResponse: {e}",
            raw_output=str(tool_input),
            provider="anthropic",
        ) from e
```

## Problem Analysis

### Root Cause

When `action` is a string but not valid JSON:
1. `json.loads(tool_input["action"])` raises `JSONDecodeError`
2. Exception is caught and silently ignored (`pass`)
3. `StepResponse.model_validate(tool_input)` is called with `action` still as a string
4. Pydantic raises `ValidationError` saying "action must be a dict"
5. The actual root cause ("action contained invalid JSON") is never logged or reported

### Why This Matters

**Debugging is harder**: When investigating failures, the error message says:
```
Failed to parse StepResponse: 1 validation error for StepResponse
action
  Input should be a valid dictionary or object to extract fields from [type=model_type, ...]
```

This doesn't tell you that the model returned a malformed JSON string. You'd have to inspect `raw_output` and notice the string-encoded action.

**Better error would be**:
```
Failed to parse StepResponse: action field was a string but contained invalid JSON:
Expecting property name enclosed in double quotes: line 1 column 2 (char 1)
Raw action string: '{action_type: "crop", x: 100}'
```

---

## Impact Assessment

### Direct Impact

- **Error clarity**: Debugging failures requires extra investigation
- **Observed frequency**: Rare (Anthropic tool use usually returns parsed dicts)
- **Consequence**: No incorrect behavior, just confusing error messages

### Risk Level

- **LOW**: Functional behavior is correct (error is raised)
- **Improvement**: Better error messages aid debugging

---

## Fix Implementation

### Option A: Log and Raise with Context (Recommended)

```python
def _parse_tool_use_to_step_response(tool_input: dict[str, Any]) -> StepResponse:
    """Parse tool use input into StepResponse.

    Handles the case where Anthropic returns nested fields as JSON strings
    instead of parsed dicts (common with complex tool schemas).

    Args:
        tool_input: The input dictionary from the tool use.

    Returns:
        Parsed StepResponse.

    Raises:
        LLMParseError: If parsing fails.
    """
    try:
        # Handle case where 'action' is returned as a JSON string instead of dict.
        # If the string is invalid JSON, raise an LLMParseError that preserves the
        # real root cause (instead of swallowing JSONDecodeError).
        if isinstance(tool_input.get("action"), str):
            action_str = tool_input["action"]
            try:
                tool_input = {
                    **tool_input,
                    "action": json.loads(action_str),
                }
            except json.JSONDecodeError as e:
                raise LLMParseError(
                    f"Anthropic tool_input.action was a string but was not valid JSON: {e}",
                    raw_output=str(tool_input),
                    provider="anthropic",
                ) from e

        return StepResponse.model_validate(tool_input)
    except ValidationError as e:
        raise LLMParseError(
            f"Failed to parse StepResponse: {e}",
            raw_output=str(tool_input),
            provider="anthropic",
        ) from e
```

### Option B: Log Warning and Continue

If we want to preserve the current "let pydantic handle it" behavior but add visibility:

```python
except json.JSONDecodeError as e:
    logger.warning(
        "action field was a string but contained invalid JSON: %s. "
        "Passing to pydantic for validation error.",
        e,
    )
    # Continue to let pydantic raise with its error
```

### Recommendation

**Option A** is preferred because:
1. Fails fast with the actual root cause
2. Avoids confusing downstream error messages
3. The raw action string is preserved for debugging

---

## Test Cases

**File**: `tests/unit/llm/test_anthropic.py`

Regression tests are implemented in the existing `TestParseToolUseToStepResponse` class (added in `733bda5a`).

```python
    def test_valid_json_string_action(self) -> None:
        """Valid JSON string action is parsed and converted."""
        tool_input = {
            "reasoning": "I see tissue",
            "action": '{"action_type": "crop", "x": 100, "y": 200, "width": 50, "height": 50}',
        }
        result = _parse_tool_use_to_step_response(tool_input)
        assert result.action.action_type == "crop"
        assert result.action.x == 100

    def test_invalid_json_string_action_raises_clear_error(self) -> None:
        """Invalid JSON string in action raises LLMParseError with clear message (BUG-038-B4)."""
        tool_input = {
            "reasoning": "I see tissue",
            "action": '{action_type: "crop", x: 100}',  # Invalid: unquoted keys
        }
        with pytest.raises(LLMParseError) as exc_info:
            _parse_tool_use_to_step_response(tool_input)

        # Error should preserve the real root cause (JSONDecodeError).
        assert "json" in str(exc_info.value).lower()
        assert exc_info.value.raw_output is not None
        assert tool_input["action"] in exc_info.value.raw_output

    def test_non_json_string_action_raises_clear_error(self) -> None:
        """Non-JSON string action raises LLMParseError."""
        tool_input = {
            "reasoning": "I see tissue",
            "action": "crop at position 100, 200",  # Plain text, not JSON
        }
        with pytest.raises(LLMParseError) as exc_info:
            _parse_tool_use_to_step_response(tool_input)

        assert "json" in str(exc_info.value).lower()
        assert exc_info.value.raw_output is not None
        assert tool_input["action"] in exc_info.value.raw_output

```

---

## Verification Steps

### 1. Confirm Regression Test Passes (current code)

```bash
uv run pytest tests/unit/llm/test_anthropic.py::TestParseToolUseToStepResponse::test_invalid_json_string_action_raises_clear_error -v
# Expected: PASS (fixed in 733bda5a)
```

### 2. (Optional) Reproduce the Original Behavior (pre-fix commit)

```bash
git switch --detach e7172a32
uv run python - <<'PY'
from giant.llm.anthropic_client import _parse_tool_use_to_step_response

tool_input = {"reasoning": "I see tissue", "action": '{action_type: "crop", x: 100}'}
try:
    _parse_tool_use_to_step_response(tool_input)
except Exception as e:
    print(type(e).__name__)
    print(str(e))
PY
# Expected: error does not include the underlying JSONDecodeError details
git switch -
```

### 3. Verify Fix

```bash
# Run all anthropic tests
uv run pytest tests/unit/llm/test_anthropic.py -v

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
- **Related**: None

---

## Sign-Off Checklist

- [x] Failing test written for `test_invalid_json_string_action_raises_clear_error`
- [x] Fix applied to `_parse_tool_use_to_step_response()`
- [x] All 8 test cases pass
- [x] Full test suite passes (`uv run pytest tests/unit`)
- [x] Type check passes (`uv run mypy src/giant`)
- [x] Lint passes (`uv run ruff check .`)
- [ ] PR created and merged
