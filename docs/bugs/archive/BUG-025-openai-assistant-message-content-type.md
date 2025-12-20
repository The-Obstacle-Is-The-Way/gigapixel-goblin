# BUG-025: OpenAI Responses API Rejects Multi-Turn Conversations

## Severity: P0 (Blocks all multi-step inference with OpenAI)

## Status: Fixed - role-aware OpenAI content typing

## Description

When running GIANT with OpenAI, the first navigation step succeeds, but all subsequent steps fail with:

```text
Error code: 400 - {'error': {'message': "Invalid value: 'input_text'. Supported values are: 'output_text' and 'refusal'.", 'type': 'invalid_request_error', 'param': 'input[1].content[0]', 'code': 'invalid_value'}}
```

This blocks all multi-step GIANT inference with OpenAI.

---

## Root Cause

Before the fix, in `src/giant/llm/converters.py`, `message_content_to_openai()` used `"type": "input_text"` for **all** text content, regardless of the message role:

```python
def message_content_to_openai(content: MessageContent) -> dict[str, Any]:
    if content.type == "text":
        if content.text is None:
            raise ValueError("Text content requires 'text' field")
        return {"type": "input_text", "text": content.text}
```

The OpenAI Responses API has different content type requirements per role:

- **User messages**: `input_text`, `input_image`
- **Assistant messages**: `output_text`, `refusal`

When the agent completes step 1 (crop action), the `ContextManager` builds an assistant message at `src/giant/agent/context.py:202-205`:

```python
return Message(
    role="assistant",
    content=[MessageContent(type="text", text=text)],
)
```

Before the fix, this assistant message gets converted via `message_to_openai()` without role-aware typing:

```python
"content": [message_content_to_openai(c) for c in message.content],
```

Since `message_content_to_openai()` did not know the role, it used `input_text` for everything. OpenAI rejects this on step 2.

---

## Reproduction

```bash
source .venv/bin/activate && source .env
giant run /path/to/any.svs -q "What tissue is this?" --provider openai
```

**Expected**: Multi-step navigation completes.
**Actual**: Step 1 succeeds, step 2+ fails with 400 error.

---

## Test Gap

Before the fix, `TestMessagesToOpenaiInput.test_preserves_order` in `tests/unit/llm/test_converters.py` only verified roles were preserved, not assistant content types:

```python
def test_preserves_order(self) -> None:
    messages = [
        Message(role="user", ...),
        Message(role="assistant", ...),  # Uses input_text internally - NOT TESTED
        Message(role="user", ...),
    ]
    result = messages_to_openai_input(messages)
    assert result[1]["role"] == "assistant"  # Only checks role, not content type
```

No test verifies that assistant messages use `output_text`.

---

## Fix Requirements

1. Modify `message_content_to_openai()` to accept a `role` parameter
2. Use `output_text` for `role="assistant"`, `input_text` for `role="user"`
3. Update `message_to_openai()` to pass the role
4. Add test case verifying assistant messages use `output_text`
5. Add test case verifying assistant messages cannot contain images (only text/refusal allowed)

---

## Files Affected

- `src/giant/llm/converters.py` - Core fix
- `tests/unit/llm/test_converters.py` - Add missing test coverage

---

## Resolution

Implemented role-aware conversion for OpenAI Responses API:

- `src/giant/llm/converters.py`: `message_content_to_openai(..., role=...)` now emits `output_text` for `role="assistant"` and rejects images for assistant messages.
- `tests/unit/llm/test_converters.py`: Added regression coverage for assistant `output_text` and unsupported assistant images.

---

## References

- [OpenAI Responses API docs](https://platform.openai.com/docs/api-reference/responses)
- Error observed during E2E testing on 2025-12-20
