# BUG-038-B12: Empty Message.content Allowed

**Status**: FIXED (2025-12-29)
**Severity**: LOW
**Component**: `src/giant/llm/protocol.py`
**Fixed In**: `3185b036` (fix: BUG-038-B12 require non-empty Message.content)
**Buggy Commit**: `85d9e074` (pre-fix)
**Current Lines (fixed)**: `protocol.py:129-137`
**Buggy Lines (pre-fix)**: `protocol.py:129-137`
**Discovered**: 2025-12-29
**Audit**: Comprehensive E2E Bug Audit (8 parallel swarm agents)
**Parent Ticket**: BUG-038

---

## Summary

Pre-fix, the `Message` model allowed `content=[]` (empty list). Provider APIs generally reject empty content blocks, so this is a footgun. Adding `min_length=1` validation catches it at construction time with a clear error.

Fixed in `3185b036` by setting `content: list[MessageContent] = Field(..., min_length=1)`.

---

## Original Code (pre-fix)

**File (pre-fix)**: `src/giant/llm/protocol.py:129-137` (commit `85d9e074`)

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

## Current Fixed Code

**File (fixed)**: `src/giant/llm/protocol.py:129-137` (commit `3185b036`)

```python
class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: list[MessageContent] = Field(..., min_length=1)
```

---

## Test Cases

**File**: `tests/unit/llm/test_protocol.py` (`TestMessage::test_empty_content_raises_validation_error`)

---

## Verification Steps

### 1. Confirm Regression Test Passes (current code)

```bash
uv run pytest tests/unit/llm/test_protocol.py::TestMessage::test_empty_content_raises_validation_error -v
# Expected: PASS (fixed in 3185b036)
```

### 2. (Optional) Reproduce the Original Behavior (pre-fix commit)

```bash
git switch --detach 85d9e074
uv run python - <<'PY'
from giant.llm.protocol import Message

msg = Message(role="user", content=[])
print(msg)
PY
# Expected: constructs successfully (pre-fix)
git switch -
```

### 3. Full Verification

```bash
uv run pytest tests/unit -x
uv run mypy src/giant
uv run ruff check .
```

---

## Dependencies

- **Blocked by**: None
- **Blocks**: None
- **Related**: None

---

## Sign-Off Checklist

- [x] Failing test written for empty content
- [x] Fix applied to `Message` model
- [x] Regression test passes
- [x] Full test suite passes (`uv run pytest tests/unit`)
- [x] Type check passes (`uv run mypy src/giant`)
- [x] Lint passes (`uv run ruff check .`)
- [ ] PR created and merged
