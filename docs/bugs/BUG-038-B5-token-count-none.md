# BUG-038-B5: None Token Counts Cause Confusing LLMError

**Status**: FIXED
**Severity**: HIGH
**Component**: `src/giant/llm/openai_client.py`, `src/giant/llm/anthropic_client.py`
**Lines**: openai_client.py:275-285, anthropic_client.py:246-256
**Discovered**: 2025-12-29
**Audit**: Comprehensive E2E Bug Audit (8 parallel swarm agents)
**Parent Ticket**: BUG-038

---

## Summary

Both LLM clients assume `usage.input_tokens` and `usage.output_tokens` are always integers. If an SDK/API edge case returns `None` for either field, computing `total_tokens` triggers a `TypeError`, which is then wrapped into an `LLMError` by the catch-all handler in `_call_with_retry()`.

This is defensive hardening: it has not been observed in saved benchmark runs, but the current failure mode is avoidable and produces a confusing error.

---

## Current Buggy Code

### OpenAI Client

**File**: `src/giant/llm/openai_client.py:275-285`

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

**File**: `src/giant/llm/anthropic_client.py:246-256`

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

## Problem Analysis

### Root Cause

The SDKs (OpenAI Python SDK and Anthropic Python SDK) type-hint `input_tokens` and `output_tokens` as `int`, but there's no runtime guarantee. In edge cases (SDK bugs, API changes, malformed responses), these could be `None`.

### When This Could Happen

1. **SDK version change**: Future SDK versions might introduce `None` as a valid value
2. **API edge cases**: Partial responses, timeouts, or error conditions
3. **Mock testing gaps**: Unit tests mock these values but integration tests might not

### Current Defensive Check

Both clients already check `if usage is None` and raise `LLMError`. The gap is that `usage` exists but `usage.input_tokens` or `usage.output_tokens` is `None`.

---

## Impact Assessment

### Direct Impact

- **Failure mode**: `TypeError` is wrapped into a generic `LLMError` (e.g., `"unsupported operand type(s) for +: 'NoneType' and 'int'"`)
- **Retries wasted**: Agent treats it as a retryable `LLMError`, consuming `max_retries` without a clear root cause
- **Cost tracking**: That call’s usage/cost cannot be computed and is not accumulated

### Observed Frequency

- **Not observed** in saved benchmark runs/artifacts
- **Theoretical risk** based on defensive programming and SDK/API edge cases

### Risk Level

- **LOW-MEDIUM**: Defensive hardening; if it occurs it turns into an `LLMError` and can trigger retries
- **High priority only if observed**: If this happens in practice, it can waste retries and obscure the real root cause

---

## Fix Implementation

### Option A: Fail Fast With Clear `LLMError` (Recommended)

```python
# OpenAI client (openai_client.py:275-285)
usage = response.usage
if usage is None:
    raise LLMError(
        "API response missing usage data - cannot track costs",
        provider="openai",
        model=self.model,
    )

prompt_tokens = usage.input_tokens
completion_tokens = usage.output_tokens

if prompt_tokens is None or completion_tokens is None:
    raise LLMError(
        "API response has None token counts "
        f"(input_tokens={prompt_tokens}, output_tokens={completion_tokens})",
        provider="openai",
        model=self.model,
    )

total_tokens = prompt_tokens + completion_tokens
```

Apply the same pattern to `src/giant/llm/anthropic_client.py` (provider `"anthropic"`).

### Option B: Default Missing Token Counts to 0 (Alternative)

```python
if prompt_tokens is None or completion_tokens is None:
    logger.warning(
        "Token count is None (input_tokens=%s, output_tokens=%s); defaulting to 0. "
        "Cost/budget tracking may be inaccurate.",
        prompt_tokens,
        completion_tokens,
    )
    prompt_tokens = prompt_tokens or 0
    completion_tokens = completion_tokens or 0
```

### Recommendation

**Option A** matches the existing strictness for missing `usage` (the run should not silently invent costs).
Use **Option B** only if continuing the run is more important than accurate cost/budget tracking.

---

## Test Cases

**File**: `tests/unit/llm/test_openai.py`

Add a new `TestOpenAITokenCounting` class near the bottom of the file (reuse the existing module fixtures `test_settings` and `sample_messages`; imports are already present in this test module).

```python
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from giant.llm.openai_client import OpenAIProvider
from giant.llm.protocol import LLMError


class TestOpenAITokenCounting:
    """Tests for token count edge cases."""

    @pytest.fixture
    def provider(self, test_settings) -> OpenAIProvider:
        """Create provider for testing."""
        return OpenAIProvider(settings=test_settings)

    @pytest.mark.asyncio
    async def test_none_input_tokens_raises_clear_llm_error(
        self, provider: OpenAIProvider, sample_messages
    ) -> None:
        """None input_tokens should raise clear LLMError (BUG-038-B5)."""
        mock_response = MagicMock()
        mock_response.output_text = (
            '{"reasoning": "test", "action": {"action_type": "answer", "answer_text": "ok"}}'
        )
        mock_response.usage = MagicMock()
        mock_response.usage.input_tokens = None  # Edge case
        mock_response.usage.output_tokens = 50

        with patch.object(
            provider._client.responses, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_response

            with pytest.raises(LLMError, match="None token counts"):
                await provider.generate_response(sample_messages)

    @pytest.mark.asyncio
    async def test_none_output_tokens_raises_clear_llm_error(
        self, provider: OpenAIProvider, sample_messages
    ) -> None:
        """None output_tokens should raise clear LLMError (BUG-038-B5)."""
        mock_response = MagicMock()
        mock_response.output_text = (
            '{"reasoning": "test", "action": {"action_type": "answer", "answer_text": "ok"}}'
        )
        mock_response.usage = MagicMock()
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = None  # Edge case

        with patch.object(
            provider._client.responses, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_response

            with pytest.raises(LLMError, match="None token counts"):
                await provider.generate_response(sample_messages)

    @pytest.mark.asyncio
    async def test_both_tokens_none_raises_clear_llm_error(
        self, provider: OpenAIProvider, sample_messages
    ) -> None:
        """Both tokens None should raise clear LLMError (BUG-038-B5)."""
        mock_response = MagicMock()
        mock_response.output_text = (
            '{"reasoning": "test", "action": {"action_type": "answer", "answer_text": "ok"}}'
        )
        mock_response.usage = MagicMock()
        mock_response.usage.input_tokens = None
        mock_response.usage.output_tokens = None

        with patch.object(
            provider._client.responses, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_response

            with pytest.raises(LLMError, match="None token counts"):
                await provider.generate_response(sample_messages)
```

**File**: `tests/unit/llm/test_anthropic.py`

Add equivalent tests for Anthropic client with same pattern.

---

## Files to Modify

| File | Lines | Change |
|------|-------|--------|
| `src/giant/llm/openai_client.py` | 275-285 | Add explicit guard for `None` token counts (Option A: raise clear `LLMError`) |
| `src/giant/llm/anthropic_client.py` | 246-256 | Add explicit guard for `None` token counts (Option A: raise clear `LLMError`) |

---

## Verification Steps

### 1. Write Failing Test First (TDD)

```bash
# Run test to confirm current implementation raises a generic LLMError
# (root cause shows up as a TypeError message).
uv run pytest tests/unit/llm/test_openai.py::TestOpenAITokenCounting::test_none_input_tokens_raises_clear_llm_error -v
# Expected: FAIL (message does not mention "None token counts")
```

### 2. Apply Fix

Edit both clients to add None handling.

### 3. Verify Fix

```bash
# Run all LLM client tests
uv run pytest tests/unit/llm/ -v

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

- [ ] Failing tests written for None token counts (OpenAI + Anthropic)
- [ ] Fix applied to `openai_client.py`
- [ ] Fix applied to `anthropic_client.py`
- [ ] All 6 test cases pass (3 per client)
- [ ] Full test suite passes (`uv run pytest tests/unit`)
- [ ] Type check passes (`uv run mypy src/giant`)
- [ ] Lint passes (`uv run ruff check .`)
- [ ] PR created and merged
