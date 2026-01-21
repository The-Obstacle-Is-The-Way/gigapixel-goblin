# BUG-048: LLM Sampling Parameters Not Explicit (Temperature / Determinism)

**Date**: 2026-01-21
**Severity**: P1 (High) — benchmark reproducibility + potential accuracy impact
**Status**: ✅ FIXED (2026-01-21)
**Discovered by**: Paper-parity audit (GIANT reproduction / underperformance)

## Summary

Both LLM provider implementations (OpenAI + Anthropic) rely on **provider defaults**
for sampling parameters (notably `temperature`). The API requests do **not** specify
temperature (or other determinism knobs like `seed`), which makes:

- Benchmark runs less reproducible (results can vary run-to-run).
- Paper comparisons harder to interpret (paper likely used fixed inference settings).
- Agent behavior potentially noisier (more invalid crops / early answers / retries),
  which can reduce measured accuracy and increase cost.

This is a **paper-parity + methodology** gap: even if the paper did not disclose the
exact temperature, we should make our inference settings explicit and configurable.

## Evidence (Current Code)

### OpenAI provider does not pass temperature

In `OpenAIProvider._call_with_retry()`, the OpenAI request omits `temperature`
(and any determinism parameters such as `seed`). See `src/giant/llm/openai_client.py:235`.

### Anthropic provider does not pass temperature

In `AnthropicProvider._call_with_retry()`, the Anthropic request omits `temperature`
as well. See `src/giant/llm/anthropic_client.py:222`.

### Settings has no sampling config

`Settings` does not expose a way to set provider sampling parameters via env vars,
so there is currently no supported way to make temperature explicit. See
`src/giant/config.py:43`.

## Why This Can Throw Off Results

GIANT is a multi-step agent loop. Non-deterministic sampling can change:

- Which regions are cropped (and therefore what evidence is seen).
- Whether outputs violate the schema (triggering retries / forced answer).
- Majority voting outcomes (`runs_per_item`) due to increased variance.

Even small changes in early steps can cascade into different trajectories and answers.

## Proposed Fix (Spec / Implementation Sketch)

1. Add explicit sampling settings:
   - `OPENAI_TEMPERATURE: float = 0.0`
   - `ANTHROPIC_TEMPERATURE: float = 0.0`
   - (Optional later) OpenAI-only: `OPENAI_SEED: int | None` for deterministic runs.

2. Thread settings into provider requests:
   - OpenAI: pass `temperature=self.settings.OPENAI_TEMPERATURE` in the
     `responses.create(...)` call. See `src/giant/llm/openai_client.py:235`.
   - Anthropic: pass `temperature=self.settings.ANTHROPIC_TEMPERATURE` in the
     `messages.create(...)` call. See `src/giant/llm/anthropic_client.py:222`.

3. Document in `CONFIG.md` under env vars:
   - Explain that paper reproduction runs should use temperature `0.0` unless
     explicitly experimenting with stochasticity.

## Fix Implemented

- Added env-configurable temperatures in `src/giant/config.py`:
  - `OPENAI_TEMPERATURE` (default `0.0`)
  - `ANTHROPIC_TEMPERATURE` (default `0.0`)
- Wired both providers to pass temperature to the underlying SDK calls:
  - OpenAI: `src/giant/llm/openai_client.py`
  - Anthropic: `src/giant/llm/anthropic_client.py`
- Added unit assertions that the SDK calls receive the configured temperature:
  - `tests/unit/llm/test_openai.py`
  - `tests/unit/llm/test_anthropic.py`

## Tests To Add

Unit tests (no live calls):

- OpenAI: assert the mocked `provider._client.responses.create(...)` call receives
  `temperature=<settings value>`.
  - Update `tests/unit/llm/test_openai.py` (existing provider-call tests already patch
    `responses.create`).

- Anthropic: assert the mocked `provider._client.messages.create(...)` call receives
  `temperature=<settings value>`.
  - Update `tests/unit/llm/test_anthropic.py` (existing provider-call tests already patch
    `messages.create`).

## Acceptance Criteria

- Providers pass explicit temperature values on every API call.
- Defaults are documented and set to `0.0` (deterministic-by-default for benchmarks).
- Unit tests assert the parameter is wired correctly.
- `make lint`, `make typecheck`, `make test` pass.
