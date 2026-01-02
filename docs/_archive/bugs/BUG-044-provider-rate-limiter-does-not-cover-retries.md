# BUG-044: Provider Rate Limiter Does Not Cover Tenacity Retries

**Date**: 2026-01-02
**Severity**: MEDIUM (P2) — increases rate-limit failures and run time/cost
**Status**: ✅ FIXED (2026-01-02)
**Discovered by**: Adversarial audit during benchmark hardening

## Summary

`OpenAIProvider` and `AnthropicProvider` apply `AsyncLimiter` **outside** the tenacity-decorated retry function. As a result, **multiple API attempts** (retries) can occur under a **single** limiter acquisition, so configured RPM limits do not reflect real request volume.

This can materially increase:
- provider 429/connection failures,
- total wall-clock time (more backoff loops),
- and failure rate (more exhausted retries),
especially during concurrent benchmark runs.

## Locations

- OpenAI provider: `src/giant/llm/openai_client.py:173` (`generate_response`) and `src/giant/llm/openai_client.py:212` (`@retry` on `_call_with_retry`)
- Anthropic provider: `src/giant/llm/anthropic_client.py:161` (`generate_response`) and `src/giant/llm/anthropic_client.py:200` (`@retry` on `_call_with_retry`)

## The Bug (What’s Wrong)

OpenAI:

```python
# src/giant/llm/openai_client.py
async def generate_response(...):
    async with self._limiter:          # <- limiter acquired once
        return await self._call_with_retry(messages)

@retry(...)
async def _call_with_retry(...):
    response = await self._client.responses.create(...)  # <- may run up to 6 times
```

Anthropic follows the same pattern:

```python
# src/giant/llm/anthropic_client.py
async def generate_response(...):
    async with self._limiter:          # <- limiter acquired once
        return await self._call_with_retry(messages)

@retry(...)
async def _call_with_retry(...):
    response = await self._client.messages.create(...)   # <- may run up to 6 times
```

Because `_call_with_retry()` is decorated with tenacity, it may perform **multiple** API requests (e.g., up to 6) while the limiter is only “charged” **once**.

## Why This Matters (Impact)

With concurrency enabled (e.g., `max_concurrent=4` in evaluation), the intended RPM cap is used to reduce 429s and stabilize throughput. If retries aren’t counted toward the limiter, the effective request rate can spike well above the configured limit during outages or high load, which can:

- increase 429 frequency (self-amplifying retry storms),
- inflate time-to-completion (more exponential backoff),
- and increase the chance that agent loops hit error-recovery paths (cost/time waste).

## Reproduction (Deterministic / Local)

You can reproduce this without live API calls by instrumenting a fake limiter and a fake client that raises `RateLimitError` N times before succeeding:

1. Patch provider `_client.<endpoint>.create` to fail twice then succeed.
2. Patch `_limiter` with an object that counts `__aenter__` invocations.
3. Call `generate_response()` once.
4. Observe: API call is attempted multiple times, but limiter `__aenter__` is invoked only once.

## Expected Behavior

Each API attempt (including retries) should be rate-limited so that total request volume respects `OPENAI_RPM` / `ANTHROPIC_RPM` under retry conditions.

## Fix

Implemented by moving limiter acquisition inside the tenacity-decorated retry
functions so each API attempt consumes rate-limit budget.

Move the limiter acquisition **inside** the tenacity-decorated function so each retry attempt reacquires rate limit budget.

Example (OpenAI):

```python
async def generate_response(...):
    self._circuit_breaker.check()
    return await self._call_with_retry(messages)

@retry(...)
async def _call_with_retry(...):
    async with self._limiter:
        response = await self._client.responses.create(...)
    ...
```

Apply the same restructuring for Anthropic.

## Tests to Add

- **Unit test** (per provider): mock `_client` to fail `k` times with `RateLimitError` before succeeding; assert limiter acquisition count equals attempts.
- Ensure parse errors (`LLMParseError`) are not retried (existing behavior) and do not consume multiple limiter acquisitions.

## Acceptance Criteria

- Under simulated retry conditions, each retry attempt reacquires the limiter.
- Benchmarks with concurrency show fewer 429 cascades (qualitative) and stable throughput vs. baseline.
- No change to parsing/validation semantics beyond rate limiting.
