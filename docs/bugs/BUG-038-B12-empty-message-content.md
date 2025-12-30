# BUG-038-B12: Empty Message.content Allowed

**Status**: DEFENSIVE (validation enhancement; not observed)
**Severity**: LOW
**Component**: `src/giant/llm/protocol.py`
**Lines**: 129-137
**Discovered**: 2025-12-29
**Audit**: Comprehensive E2E Bug Audit (8 parallel swarm agents)
**Parent Ticket**: BUG-038

---

## Summary

The `Message` model allows `content=[]` (empty list). Provider APIs generally reject empty content blocks, so this is a footgun for future changes. Adding `min_length=1` validation would catch it early with a clear message.

---

## Current Code

**File**: `src/giant/llm/protocol.py:129-137`

```python
class Message(BaseModel):
    """A message in the conversation with the LLM.

    Messages can contain multiple content items (text and images).
    The role indicates who sent the message.
    """

    role: Literal["system", "user", "assistant"]
    content: list[MessageContent]
```

---

## Problem Analysis

### Current Behavior

```python
# This is valid but will fail at API call time
msg = Message(role="user", content=[])
```

At API call time, providers typically reject empty content arrays (exact error text may vary by SDK/API version).

### Better Behavior

Fail at construction time with clear error:
```
ValidationError: content
  List should have at least 1 item after validation, not 0 [type=too_short, ...]
```

---

## Impact Assessment

### Direct Impact

- **None currently**: No occurrences of `content=[]` found in `src/` during this audit
- **Future safety**: Prevents accidental empty messages

### When This Could Happen

1. **Bug in ContextManager**: Logic error produces empty content
2. **Direct Message construction**: Developer forgets to add content
3. **Serialization error**: JSON with `"content": []`

### Risk Level

- **VERY LOW**: Defensive validation

---

## Fix Implementation

### Add min_length Constraint

```python
from pydantic import BaseModel, Field

class Message(BaseModel):
    """A message in the conversation with the LLM.

    Messages can contain multiple content items (text and images).
    The role indicates who sent the message.
    """

    role: Literal["system", "user", "assistant"]
    content: list[MessageContent] = Field(..., min_length=1)
```

---

## Test Cases

**File**: `tests/unit/llm/test_protocol.py`

Add this test method to the existing `TestMessage` class.

```python
    def test_empty_content_raises_validation_error(self) -> None:
        """Empty content list should raise ValidationError (BUG-038-B12)."""
        with pytest.raises(ValidationError) as exc_info:
            Message(role="user", content=[])

        # Check error mentions min_length / too_short
        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("content",)
        assert "too_short" in errors[0]["type"] or "min_length" in str(errors[0])
```

---

## Files to Modify

| File | Lines | Change |
|------|-------|--------|
| `src/giant/llm/protocol.py` | 137 | Add `Field(..., min_length=1)` to content |

---

## Verification Steps

### 1. Write Failing Test First (TDD)

```bash
# Run test to confirm current implementation allows empty content
uv run pytest tests/unit/llm/test_protocol.py::TestMessage::test_empty_content_raises_validation_error -v
# Expected: FAIL (no ValidationError raised)
```

### 2. Apply Fix

Add `Field(..., min_length=1)` constraint.

### 3. Verify Fix

```bash
# Run all protocol tests
uv run pytest tests/unit/llm/test_protocol.py -v

# Run full test suite (check for regressions)
uv run pytest tests/unit -x

# Type check
uv run mypy src/giant

# Lint
uv run ruff check .
```

---

## Regression Risk

**Check these files for empty content construction:**

```bash
rg -n "content=\\[\\]" src/
rg -n "content: \\[\\]" src/
```

If any code intentionally creates `content=[]`, it must be updated.

---

## Dependencies

- **Blocked by**: None
- **Blocks**: None
- **Related**: None

---

## Sign-Off Checklist

- [ ] Failing test written for empty content
- [ ] Fix applied to `Message` model
- [ ] Regression check: no code creates `content=[]`
- [ ] New validation test passes
- [ ] Full test suite passes (`uv run pytest tests/unit`)
- [ ] Type check passes (`uv run mypy src/giant`)
- [ ] Lint passes (`uv run ruff check .`)
- [ ] PR created and merged
