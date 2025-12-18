# BUG-013: Silent Zero-Cost Reporting on Missing Usage Data

## Severity: P1 (High Priority) - Cost Tracking Integrity

## Status: Open

## Description

Both OpenAI and Anthropic providers have defensive None checks for usage data that silently report 0 tokens and $0.00 cost if the SDK ever returns None usage. This breaks cost tracking without any error or warning.

### Current Code

```python
# src/giant/llm/openai_client.py:204-208
usage = response.usage
prompt_tokens = usage.input_tokens if usage else 0
completion_tokens = usage.output_tokens if usage else 0
total_tokens = prompt_tokens + completion_tokens

# src/giant/llm/anthropic_client.py:224-228
# Same pattern with comment "defensive None check for SDK edge cases"
usage = response.usage
prompt_tokens = usage.input_tokens if usage else 0
completion_tokens = usage.output_tokens if usage else 0
```

### Why This Is Bad

1. **Silent Data Loss**: If SDK returns None usage (API change, SDK bug, etc.), cost tracking silently breaks
2. **No Warning**: User sees $0.00 cost with no indication something is wrong
3. **Budget Guardrails Fail**: Spec-09's `budget_usd` feature depends on accurate cost tracking
4. **Production Money Burn**: Could spend real money while reporting $0.00 spent

### Expected Behavior

Either:
1. **Raise Error**: Usage data is required for cost tracking - fail loudly
2. **Log Warning**: Accept zero but log a clear warning that usage was missing

### Proposed Fix

```python
# Option A: Fail fast (recommended for production integrity)
usage = response.usage
if usage is None:
    raise LLMError(
        "API response missing usage data - cannot track costs",
        provider="openai",
        model=self.model,
    )
prompt_tokens = usage.input_tokens
completion_tokens = usage.output_tokens

# Option B: Warn but continue (if SDK None is expected edge case)
usage = response.usage
if usage is None:
    logger.warning(
        "API response missing usage data, reporting 0 tokens",
        provider="openai",
        model=self.model,
    )
    prompt_tokens = 0
    completion_tokens = 0
else:
    prompt_tokens = usage.input_tokens
    completion_tokens = usage.output_tokens
```

### Impact

- **P0 → P1**: Downgraded from P0 because SDKs reliably return usage today
- Cost tracking integrity is critical for Spec-09's budget guardrails
- Budget overflow could cause unlimited spend if this triggers

### Code Location

- `src/giant/llm/openai_client.py:204-208`
- `src/giant/llm/anthropic_client.py:224-228`

### Test Evidence

Current tests always mock usage data. No test exercises None usage path.

### Mitigation

Add integration tests that verify usage is always present in real API responses.
