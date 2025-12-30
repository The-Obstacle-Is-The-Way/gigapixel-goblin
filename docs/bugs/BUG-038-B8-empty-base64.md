# BUG-038-B8: Empty Base64 Not Caught Early

**Status**: CONFIRMED (not yet fixed)
**Severity**: MEDIUM
**Component**: `src/giant/llm/converters.py`
**Lines**: 247-269
**Discovered**: 2025-12-29
**Audit**: Comprehensive E2E Bug Audit (8 parallel swarm agents)
**Parent Ticket**: BUG-038

---

## Summary

The `count_image_pixels_in_messages()` function checks for `None` in `image_base64` but not for empty string `""`. An empty string decodes to zero bytes, which causes `Image.open()` to fail with a confusing error instead of a clear validation error.

---

## Current Buggy Code

**File**: `src/giant/llm/converters.py:247-269`

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

## Problem Analysis

### Root Cause

1. `content.image_base64 = ""` passes the `is None` check
2. `base64.b64decode("")` returns `b""` (empty bytes) - no error
3. `Image.open(BytesIO(b""))` raises `UnidentifiedImageError`
4. Error message is confusing: "cannot identify image file" instead of "empty base64"

### Error Propagation

```
PIL.UnidentifiedImageError: cannot identify image file <_io.BytesIO object at 0x...>
```

This error doesn't indicate that the image data was empty.

---

## Impact Assessment

### Direct Impact

- **Confusing errors**: Developer sees "cannot identify image file" not "empty image data"
- **Debugging difficulty**: Must inspect the actual base64 string to understand failure

### When This Could Happen

1. **Corrupted data**: Image crop returned empty bytes
2. **Bug in upstream**: WSIReader returns empty content
3. **Serialization error**: JSON with `"image_base64": ""`

### Risk Level

- **MEDIUM**: Defensive programming, rare edge case
- **No production occurrences** observed

---

## Fix Implementation

### Simple Fix: Check for Empty String

```python
def count_image_pixels_in_messages(messages: list[Message]) -> int:
    """Count total pixels across all images in a message list.

    Useful for Anthropic cost calculation, which is pixel-based.

    Raises:
        ValueError: If any image_base64 is invalid, empty, or not decodable as an image.
    """
    total_pixels = 0
    for message in messages:
        for content in message.content:
            if content.type != "image":
                continue
            if content.image_base64 is None:
                raise ValueError("Image content requires 'image_base64' field")
            if content.image_base64 == "":  # Check for empty string
                raise ValueError("Image content has empty 'image_base64' field")
            try:
                image_bytes = base64.b64decode(content.image_base64, validate=True)
            except binascii.Error as e:
                raise ValueError("Invalid base64 image data") from e
            if not image_bytes:  # Defensive: check decoded bytes are not empty
                raise ValueError("Image base64 decoded to empty bytes")
            with Image.open(BytesIO(image_bytes)) as image:
                width, height = image.size
            total_pixels += width * height
    return total_pixels
```

---

## Test Cases

**File**: `tests/unit/llm/test_converters.py`

Add these test methods to the existing `TestCountImagePixelsInMessages` class.

```python
    def test_empty_string_base64_raises_clear_error(self) -> None:
        """Empty string base64 should raise ValueError with clear message (BUG-038-B8)."""
        messages = [
            Message(
                role="user",
                content=[
                    MessageContent(type="image", image_base64=""),  # Empty string
                ],
            )
        ]
        with pytest.raises(ValueError, match="empty"):
            count_image_pixels_in_messages(messages)

    def test_none_base64_raises_clear_error(self) -> None:
        """None base64 should raise ValueError."""
        messages = [
            Message(
                role="user",
                content=[
                    MessageContent(type="image", image_base64=None),
                ],
            )
        ]
        with pytest.raises(ValueError, match="requires"):
            count_image_pixels_in_messages(messages)
```

---

## Files to Modify

| File | Lines | Change |
|------|-------|--------|
| `src/giant/llm/converters.py` | 247-269 | Add empty string + empty bytes checks in `count_image_pixels_in_messages()` |

---

## Verification Steps

### 1. Write Failing Test First (TDD)

```bash
# Run test to confirm current implementation gives confusing error
uv run pytest tests/unit/llm/test_converters.py::TestCountImagePixelsInMessages::test_empty_string_base64_raises_clear_error -v
# Expected: FAIL (raises UnidentifiedImageError not ValueError with "empty")
```

### 2. Apply Fix

Add empty string and empty bytes checks.

### 3. Verify Fix

```bash
# Run all converter tests
uv run pytest tests/unit/llm/test_converters.py -v

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

- [ ] Failing tests written for empty base64
- [ ] Fix applied to `count_image_pixels_in_messages()`
- [ ] All 4 test cases in `TestCountImagePixelsInMessages` pass
- [ ] Full test suite passes (`uv run pytest tests/unit`)
- [ ] Type check passes (`uv run mypy src/giant`)
- [ ] Lint passes (`uv run ruff check .`)
- [ ] PR created and merged
