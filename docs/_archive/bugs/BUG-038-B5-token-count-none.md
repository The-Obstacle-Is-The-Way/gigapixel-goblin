# BUG-038-B5: None Token Counts Cause Confusing LLMError

**Status**: FIXED (2025-12-29)
**Severity**: HIGH
**Component**: `src/giant/llm/openai_client.py`, `src/giant/llm/anthropic_client.py`
**Fixed In**: `f1741576` (fix: BUG-038-B5 guard against None token counts in LLM clients)
**Buggy Commit**: `3dc948de` (pre-fix)
**Current Lines (fixed)**: `openai_client.py:275-295`, `anthropic_client.py:246-266`
**Buggy Lines (pre-fix)**: `openai_client.py:275-285`, `anthropic_client.py:246-256`
**Discovered**: 2025-12-29
**Audit**: Comprehensive E2E Bug Audit (8 parallel swarm agents)
**Parent Ticket**: BUG-038

---

## Summary

Pre-fix, both LLM clients assumed `usage.input_tokens` and `usage.output_tokens` were always integers. If an SDK/API edge case returned `None` for either field, `total_tokens = prompt_tokens + completion_tokens` raised a `TypeError`. That `TypeError` was then wrapped into a generic `LLMError`, which the agent loop retried up to `max_retries`, obscuring root cause and wasting retries.

Fixed in `f1741576` by explicitly checking for `None` token counts and raising a clear `LLMError` before doing arithmetic / cost accounting.

---

## Original Buggy Code (pre-fix)

### OpenAI Client

**File (pre-fix)**: `src/giant/llm/openai_client.py:275-285` (commit `3dc948de`)

```python
# Calculate usage and cost
usage = response.usage
if usage is None:
    raise LLMError(
        "API response missing usage data - cannot track costs",
        provider="openai",
        model=self.model,
    )
prompt_tokens = usage.input_tokens
completion_tokens = usage.output_tokens
total_tokens = prompt_tokens + completion_tokens
```

### Anthropic Client

**File (pre-fix)**: `src/giant/llm/anthropic_client.py:246-256` (commit `3dc948de`)

```python
# Calculate usage and cost (defensive None check for SDK edge cases)
usage = response.usage
if usage is None:
    raise LLMError(
        "API response missing usage data - cannot track costs",
        provider="anthropic",
        model=self.model,
    )
prompt_tokens = usage.input_tokens
completion_tokens = usage.output_tokens
total_tokens = prompt_tokens + completion_tokens
```

---

## Current Fixed Code

### OpenAI Client

**File (fixed)**: `src/giant/llm/openai_client.py:275-295` (commit `f1741576`)

```python
prompt_tokens = usage.input_tokens
completion_tokens = usage.output_tokens

if prompt_tokens is None or completion_tokens is None:
    raise LLMError(
        "API response has None token counts "
        f"(input={prompt_tokens}, output={completion_tokens})",
        provider="openai",
        model=self.model,
    )

total_tokens = prompt_tokens + completion_tokens
```

### Anthropic Client

**File (fixed)**: `src/giant/llm/anthropic_client.py:246-266` (commit `f1741576`)

```python
prompt_tokens = usage.input_tokens
completion_tokens = usage.output_tokens

if prompt_tokens is None or completion_tokens is None:
    raise LLMError(
        "API response has None token counts "
        f"(input={prompt_tokens}, output={completion_tokens})",
        provider="anthropic",
        model=self.model,
    )

total_tokens = prompt_tokens + completion_tokens
```

---

## Problem Analysis

### Root Cause

The OpenAI and Anthropic SDKs type-hint token counts as `int`, but there is no runtime guarantee. In edge cases (SDK bug, API change, malformed/partial responses, mocks), either field can be `None`.

### Why This Matters in GIANT

The agent loop treats `LLMError`/`LLMParseError` as retryable up to `max_retries`. A `TypeError` wrapped into a generic provider failure produces a confusing message (e.g., `unsupported operand type(s) for +: 'NoneType' and 'int'`) and wastes retries without exposing the actual root cause.

---

## Fix Implementation

### Option A: Fail Fast With Clear `LLMError` (Implemented)

Add an explicit `None` guard for `prompt_tokens` / `completion_tokens`, mirroring the existing strictness for missing `usage`.

### Option B: Default Missing Token Counts to 0 (Not Implemented)

Only consider this if continuing the run is more important than accurate cost/budget tracking.

---

## Test Cases

**Files**:
- `tests/unit/llm/test_openai.py` (`TestOpenAITokenCounting`)
- `tests/unit/llm/test_anthropic.py` (`TestAnthropicTokenCounting`)

The regression tests patch the SDK client call and return a `usage` object where `input_tokens` and/or `output_tokens` is `None`. Expected behavior is a clear `LLMError` mentioning "None token counts".

---

## Verification Steps

### 1. Confirm Regression Tests Pass (current code)

```bash
uv run pytest tests/unit/llm/test_openai.py::TestOpenAITokenCounting -v
uv run pytest tests/unit/llm/test_anthropic.py::TestAnthropicTokenCounting -v
# Expected: PASS (fixed in f1741576)
```

### 2. (Optional) Reproduce the Original Failure (pre-fix commit)

```bash
git switch --detach 3dc948de
uv run python - <<'PY'
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from giant.config import Settings
from giant.llm.openai_client import OpenAIProvider
from giant.llm.protocol import Message, MessageContent


async def main() -> None:
    provider = OpenAIProvider(
        settings=Settings(
            OPENAI_API_KEY="test-key",
            ANTHROPIC_API_KEY="test-key",
            OPENAI_RPM=1000,
            IMAGE_SIZE_OPENAI=1000,
            _env_file=None,  # type: ignore[call-arg]
        )
    )

    messages = [
        Message(
            role="system",
            content=[MessageContent(type="text", text="You are a pathologist.")],
        ),
        Message(
            role="user",
            content=[MessageContent(type="text", text="What do you see?")],
        ),
    ]

    mock_response = MagicMock()
    mock_response.output_text = (
        '{"reasoning": "test", "action": {"action_type": "answer", "answer_text": "ok"}}'
    )
    mock_response.usage = MagicMock(input_tokens=None, output_tokens=50)

    with patch.object(
        provider._client.responses, "create", new_callable=AsyncMock
    ) as mock_create:
        mock_create.return_value = mock_response
        await provider.generate_response(messages)


asyncio.run(main())
PY
# Expected: LLMError wrapping a TypeError about NoneType + int
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

- [x] Failing tests written for None token counts (OpenAI + Anthropic)
- [x] Fix applied to `src/giant/llm/openai_client.py`
- [x] Fix applied to `src/giant/llm/anthropic_client.py`
- [x] All 6 test cases pass (3 per client)
- [x] Full test suite passes (`uv run pytest tests/unit`)
- [x] Type check passes (`uv run mypy src/giant`)
- [x] Lint passes (`uv run ruff check .`)
- [ ] PR created and merged
