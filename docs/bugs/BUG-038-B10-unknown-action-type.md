# BUG-038-B10: Unknown Action Type Error Clarity

**Status**: FIXED (2025-12-29)
**Severity**: MEDIUM
**Component**: `src/giant/llm/openai_client.py`
**Lines**: 72-112 (`_normalize_openai_response`)
**Discovered**: 2025-12-29
**Audit**: Comprehensive E2E Bug Audit (8 parallel swarm agents)
**Parent Ticket**: BUG-038

---

## Summary

When OpenAI returns an unknown `action_type` (not `"crop"` or `"answer"`), `_normalize_openai_response()` passes it through unchanged and the error is raised later by `StepResponse.model_validate()`.

This is correct behavior (the response is invalid), but the resulting pydantic discriminator error is confusing for users debugging LLM outputs. This spec is about raising a clearer `LLMParseError` that explicitly says “unknown action_type”.

---

## Current Code

**File**: `src/giant/llm/openai_client.py:72-112`

```python
def _normalize_openai_response(data: dict[str, Any]) -> dict[str, Any]:
    """Convert OpenAI's flattened response to StepResponse-compatible format.

    The OpenAI schema has all action fields present with nulls for unused ones.
    This function filters out the null fields so pydantic can validate properly.

    Args:
        data: Raw parsed JSON from OpenAI response.

    Returns:
        Normalized dict suitable for StepResponse.model_validate().
    """
    if "action" not in data or not isinstance(data["action"], dict):
        return data

    action = data["action"]
    action_type = action.get("action_type")

    if action_type == "crop":
        # Keep only crop fields
        normalized_action = {
            "action_type": "crop",
            "x": action.get("x"),
            "y": action.get("y"),
            "width": action.get("width"),
            "height": action.get("height"),
        }
    elif action_type == "answer":
        # Keep only answer fields
        normalized_action = {
            "action_type": "answer",
            "answer_text": action.get("answer_text"),
        }
    else:
        # Unknown action type, pass through as-is
        normalized_action = action

    return {
        "reasoning": data.get("reasoning"),
        "action": normalized_action,
    }
```

---

## Problem Analysis

### Current Error (Confusing)

When `action_type="zoom"` (unknown), pydantic raises:

```
Failed to parse StepResponse: 1 validation error for StepResponse
action
  Input tag 'zoom' found using 'action_type' does not match any of the expected tags: 'crop', 'answer' [type=union_tag_invalid, ...]
```

This is technically correct but:
1. "Input tag" terminology is confusing
2. Doesn't say "LLM returned unknown action type"
3. Error source is unclear (OpenAI? Our code? Schema?)

### Better Error

```
LLMParseError: Unknown action_type 'zoom'. Expected 'crop' or 'answer'.
Raw action: {"action_type": "zoom", "level": 2}
```

---

## Impact Assessment

### Direct Impact

- **Confusing errors**: Developers must understand pydantic discriminators
- **Debugging difficulty**: Error doesn't clearly point to LLM output

### When This Could Happen

1. **Schema drift**: LLM trained on different action types
2. **Prompt injection**: Adversarial input causing unexpected outputs
3. **Model hallucination**: LLM invents action types

### Risk Level

- **LOW**: Very rare occurrence
- **Improvement**: Better error messages

---

## Fix Implementation

### Raise Early with Clear Error

```python
def _normalize_openai_response(data: dict[str, Any]) -> dict[str, Any]:
    """Convert OpenAI's flattened response to StepResponse-compatible format.

    The OpenAI schema has all action fields present with nulls for unused ones.
    This function filters out the null fields so pydantic can validate properly.

    Args:
        data: Raw parsed JSON from OpenAI response.

    Returns:
        Normalized dict suitable for StepResponse.model_validate().

    Raises:
        LLMParseError: If action_type is unknown.
    """
    if "action" not in data or not isinstance(data["action"], dict):
        return data

    action = data["action"]
    action_type = action.get("action_type")

    if action_type == "crop":
        normalized_action = {
            "action_type": "crop",
            "x": action.get("x"),
            "y": action.get("y"),
            "width": action.get("width"),
            "height": action.get("height"),
        }
    elif action_type == "answer":
        normalized_action = {
            "action_type": "answer",
            "answer_text": action.get("answer_text"),
        }
    else:
        # Raise clear error instead of confusing pydantic discriminator error
        raise LLMParseError(
            f"Unknown action_type '{action_type}'. Expected 'crop' or 'answer'.",
            raw_output=str(action),
            provider="openai",
        )

    return {
        "reasoning": data.get("reasoning"),
        "action": normalized_action,
    }
```

No caller changes are required: `_call_with_retry()` already propagates `LLMParseError` and the agent treats it as a retryable failure.

---

## Test Cases

**File**: `tests/unit/llm/test_openai.py`

```python
import pytest

from giant.llm.openai_client import _normalize_openai_response
from giant.llm.protocol import LLMParseError


class TestNormalizeOpenAIResponse:
    """Tests for _normalize_openai_response helper."""

    def test_crop_action_normalized(self) -> None:
        """Crop action is normalized correctly."""
        data = {
            "reasoning": "I see something",
            "action": {
                "action_type": "crop",
                "x": 100,
                "y": 200,
                "width": 50,
                "height": 50,
                "answer_text": None,  # OpenAI includes nulls
            },
        }
        result = _normalize_openai_response(data)
        assert result["action"]["action_type"] == "crop"
        assert "answer_text" not in result["action"]  # Null filtered out

    def test_answer_action_normalized(self) -> None:
        """Answer action is normalized correctly."""
        data = {
            "reasoning": "This is benign",
            "action": {
                "action_type": "answer",
                "answer_text": "Benign tissue",
                "x": None,
                "y": None,
                "width": None,
                "height": None,
            },
        }
        result = _normalize_openai_response(data)
        assert result["action"]["action_type"] == "answer"
        assert result["action"]["answer_text"] == "Benign tissue"
        assert "x" not in result["action"]  # Null filtered out

    def test_unknown_action_type_raises_clear_error(self) -> None:
        """Unknown action_type raises LLMParseError with clear message (BUG-038-B10)."""
        data = {
            "reasoning": "I want to zoom",
            "action": {
                "action_type": "zoom",  # Unknown
                "level": 2,
            },
        }
        with pytest.raises(LLMParseError) as exc_info:
            _normalize_openai_response(data)

        assert "Unknown action_type" in str(exc_info.value)
        assert "zoom" in str(exc_info.value)
        assert "crop" in str(exc_info.value) or "answer" in str(exc_info.value)

    def test_none_action_type_raises_clear_error(self) -> None:
        """None action_type raises LLMParseError."""
        data = {
            "reasoning": "No action",
            "action": {
                "action_type": None,
            },
        }
        with pytest.raises(LLMParseError) as exc_info:
            _normalize_openai_response(data)

        assert "Unknown action_type" in str(exc_info.value)

    def test_missing_action_type_raises_clear_error(self) -> None:
        """Missing action_type raises LLMParseError."""
        data = {
            "reasoning": "Bad action",
            "action": {
                "x": 100,  # No action_type
            },
        }
        with pytest.raises(LLMParseError) as exc_info:
            _normalize_openai_response(data)

        assert "Unknown action_type" in str(exc_info.value)

    def test_missing_action_key_returns_data(self) -> None:
        """Missing 'action' key passes through (let pydantic handle)."""
        data = {"reasoning": "No action key"}
        result = _normalize_openai_response(data)
        assert result == data

    def test_non_dict_action_returns_data(self) -> None:
        """Non-dict action passes through (let pydantic handle)."""
        data = {"reasoning": "Bad action", "action": "not a dict"}
        result = _normalize_openai_response(data)
        assert result == data
```

---

## Files to Modify

| File | Lines | Change |
|------|-------|--------|
| `src/giant/llm/openai_client.py` | 105-107 | Raise `LLMParseError` for unknown action types |

---

## Verification Steps

### 1. Write Failing Test First (TDD)

```bash
# Run test to confirm current implementation gives confusing error
uv run pytest tests/unit/llm/test_openai.py::TestNormalizeOpenAIResponse::test_unknown_action_type_raises_clear_error -v
# Expected: FAIL (no LLMParseError raised; unknown action_type passes through)
```

### 2. Apply Fix

Modify `_normalize_openai_response` to raise `LLMParseError`.

### 3. Verify Fix

```bash
# Run all OpenAI tests
uv run pytest tests/unit/llm/test_openai.py -v

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
- **Related**: B4 (similar error clarity issue for Anthropic)

---

## Sign-Off Checklist

- [x] Failing tests written for unknown action_type
- [x] Fix applied to `_normalize_openai_response()`
- [x] All 7 test cases pass
- [x] Full test suite passes (`uv run pytest tests/unit`)
- [x] Type check passes (`uv run mypy src/giant`)
- [x] Lint passes (`uv run ruff check .`)
- [ ] PR created and merged
