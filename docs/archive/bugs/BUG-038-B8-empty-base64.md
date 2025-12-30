# BUG-038-B8: Empty Base64 Not Caught Early

**Status**: FIXED (2025-12-29)
**Severity**: MEDIUM
**Component**: `src/giant/llm/converters.py`
**Fixed In**: `85d9e074` (fix: BUG-038-B8 validate empty base64 image data early)
**Buggy Commit**: `f1741576` (pre-fix)
**Current Lines (fixed)**: `converters.py:247-273`
**Buggy Lines (pre-fix)**: `converters.py:247-269`
**Discovered**: 2025-12-29
**Audit**: Comprehensive E2E Bug Audit (8 parallel swarm agents)
**Parent Ticket**: BUG-038

---

## Summary

Pre-fix, `count_image_pixels_in_messages()` validated `image_base64 is None` but did not validate `image_base64 == ""`. An empty string decodes to `b""`, which then fails in `PIL.Image.open()` with a confusing `UnidentifiedImageError` instead of a clear validation error.

Fixed in `85d9e074` by rejecting empty base64 strings (and defensively rejecting decoded empty bytes) before calling `Image.open()`.

---

## Original Buggy Code (pre-fix)

**File (pre-fix)**: `src/giant/llm/converters.py:247-269` (commit `f1741576`)

```python
def count_image_pixels_in_messages(messages: list[Message]) -> int:
    """Count total pixels across all images in a message list.

    Useful for Anthropic cost calculation, which is pixel-based.

    Raises:
        ValueError: If any image_base64 is invalid or not decodable as an image.
    """
    total_pixels = 0
    for message in messages:
        for content in message.content:
            if content.type != "image":
                continue
            if content.image_base64 is None:
                raise ValueError("Image content requires 'image_base64' field")
            try:
                image_bytes = base64.b64decode(content.image_base64, validate=True)
            except binascii.Error as e:
                raise ValueError("Invalid base64 image data") from e
            with Image.open(BytesIO(image_bytes)) as image:
                width, height = image.size
            total_pixels += width * height
    return total_pixels
```

---

## Current Fixed Code

**File (fixed)**: `src/giant/llm/converters.py:247-273` (commit `85d9e074`)

```python
if content.image_base64 is None:
    raise ValueError("Image content requires 'image_base64' field")
if content.image_base64 == "":
    raise ValueError("Image content has empty 'image_base64' field")
try:
    image_bytes = base64.b64decode(content.image_base64, validate=True)
except binascii.Error as e:
    raise ValueError("Invalid base64 image data") from e
if not image_bytes:
    raise ValueError("Image base64 decoded to empty bytes")
with Image.open(BytesIO(image_bytes)) as image:
    width, height = image.size
```

---

## Problem Analysis

### Root Cause

1. `content.image_base64 = ""` passes the `is None` check
2. `base64.b64decode("")` returns `b""` (empty bytes) without error
3. `Image.open(BytesIO(b""))` raises `PIL.UnidentifiedImageError`
4. The exception message does not indicate the true cause (empty base64 payload)

---

## Test Cases

**File**: `tests/unit/llm/test_converters.py` (`TestCountImagePixelsInMessages`)

Regression tests assert that empty base64 strings fail fast with `ValueError` and a clear message, rather than bubbling `UnidentifiedImageError`.

---

## Verification Steps

### 1. Confirm Regression Tests Pass (current code)

```bash
uv run pytest tests/unit/llm/test_converters.py::TestCountImagePixelsInMessages::test_empty_string_base64_raises_clear_error -v
uv run pytest tests/unit/llm/test_converters.py::TestCountImagePixelsInMessages::test_none_base64_raises_clear_error -v
# Expected: PASS (fixed in 85d9e074)
```

### 2. (Optional) Reproduce the Original Failure (pre-fix commit)

```bash
git switch --detach f1741576
uv run python - <<'PY'
from giant.llm.converters import count_image_pixels_in_messages
from giant.llm.protocol import Message, MessageContent

messages = [
    Message(role="user", content=[MessageContent(type="image", image_base64="")]),
]

count_image_pixels_in_messages(messages)
PY
# Expected: PIL.UnidentifiedImageError (empty bytes passed into Image.open)
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

- [x] Failing tests written for empty base64
- [x] Fix applied to `count_image_pixels_in_messages()`
- [x] Regression tests pass (`tests/unit/llm/test_converters.py`)
- [x] Full test suite passes (`uv run pytest tests/unit`)
- [x] Type check passes (`uv run mypy src/giant`)
- [x] Lint passes (`uv run ruff check .`)
- [ ] PR created and merged
