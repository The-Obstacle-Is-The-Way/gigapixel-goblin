# Spec-08.5: LLM Pipeline Integration Checkpoint

## Overview

**This is a PAUSE POINT.** Before proceeding to Spec-09 (GIANT Agent), complete all integration tests below to catch P0-P4 issues in the LLM pipeline (Specs 06-08).

**Why pause here?**
- Specs 06-08 form a complete subsystem: provider → prompts → context management
- Spec-09 merges WSI + LLM pipelines — debugging becomes exponentially harder
- API edge cases (rate limits, token overflows, malformed responses) must be caught now
- Cost estimation bugs here lead to real money wasted in production

## Prerequisites

- [ ] Spec-05.5: WSI Integration Checkpoint — PASSED
- [ ] Spec-06: LLM Provider Abstraction — merged to main
- [ ] Spec-07: Navigation Prompt Engineering — merged to main
- [ ] Spec-08: Conversation Context Manager — merged to main
- [ ] All unit tests passing with ≥90% coverage

## Integration Test Checklist

### P0: Critical Path (Must Pass)

These tests validate the agent loop can function.

| ID | Test | Command/Steps | Expected | Status |
|----|------|---------------|----------|--------|
| P0-1 | **OpenAI provider init** | `OpenAIProvider(api_key=...)` | Initializes without error | [ ] |
| P0-2 | **Anthropic provider init** | `AnthropicProvider(api_key=...)` | Initializes without error | [ ] |
| P0-3 | **Send text message** | `provider.generate(messages=[text_only])` | Returns valid response | [ ] |
| P0-4 | **Send image message** | `provider.generate(messages=[with_image])` | Returns valid response with image analysis | [ ] |
| P0-5 | **System prompt applied** | Build system message, verify in API call | System message in first position | [ ] |
| P0-6 | **User prompt construction** | `build_user_message(question, step, max_steps)` | Contains question, step count, instructions | [ ] |
| P0-7 | **Context accumulation** | Add 3 turns to ContextManager | `get_messages()` returns alternating user/assistant | [ ] |
| P0-8 | **Parse crop action** | Model returns `crop(x, y, w, h)` | Parses to Region object | [ ] |
| P0-9 | **Parse answer action** | Model returns `answer(text)` | Extracts final answer | [ ] |

### P1: High Priority (Should Pass)

Edge cases that will cause production failures.

| ID | Test | Command/Steps | Expected | Status |
|----|------|---------------|----------|--------|
| P1-1 | **Rate limit handling** | Trigger 429 response | Retry with backoff, eventually succeeds | [ ] |
| P1-2 | **Token limit approach** | Build context near max tokens | Warns or truncates gracefully | [ ] |
| P1-3 | **Image pruning** | Set `max_history_images=3`, add 5 turns | Older images replaced with placeholder | [ ] |
| P1-4 | **Malformed model response** | Mock response without valid action | Returns error, doesn't crash | [ ] |
| P1-5 | **Empty model response** | Mock empty string response | Returns error, doesn't crash | [ ] |
| P1-6 | **Invalid coordinates in crop** | Model returns `crop(-100, -100, 500, 500)` | Validation catches, returns error | [ ] |
| P1-7 | **Cost tracking** | Run 5 API calls | Accumulated cost matches expected | [ ] |
| P1-8 | **Provider switching** | Same context, different provider | Both produce valid responses | [ ] |

### P2: Medium Priority (Edge Cases)

Less common scenarios that could cause issues.

| ID | Test | Command/Steps | Expected | Status |
|----|------|---------------|----------|--------|
| P2-1 | **Very long question** | Question > 1000 tokens | Truncated or error, doesn't crash | [ ] |
| P2-2 | **Unicode in question** | Question with emoji, CJK chars | Handles correctly | [ ] |
| P2-3 | **20 iteration context** | Full 20-step conversation | Context builds correctly, token count reasonable | [ ] |
| P2-4 | **Trajectory serialization** | Dump trajectory to JSON, reload | Roundtrips perfectly | [ ] |
| P2-5 | **Concurrent API calls** | 3 simultaneous generate() calls | All complete (may be rate limited) | [ ] |
| P2-6 | **API timeout** | Mock 30s+ response time | Times out gracefully | [ ] |
| P2-7 | **Network error** | Mock connection failure | Retries, then clean error | [ ] |

### P3: Low Priority (Nice to Have)

Performance and robustness.

| ID | Test | Command/Steps | Expected | Status |
|----|------|---------------|----------|--------|
| P3-1 | **Token estimation accuracy** | Compare estimated vs actual usage | Within 10% | [ ] |
| P3-2 | **Cost estimation accuracy** | Compare estimated vs actual cost | Within 5% | [ ] |
| P3-3 | **Prompt caching (Anthropic)** | Same system prompt, multiple calls | Cache hits logged | [ ] |
| P3-4 | **Response streaming** | If implemented, verify stream works | Chunks arrive incrementally | [ ] |

### P4: Stretch (Future-Proofing)

Won't block progress but good to note.

| ID | Test | Notes | Status |
|----|------|-------|--------|
| P4-1 | **Gemini provider** | Not in current spec | Document as future work | [ ] |
| P4-2 | **Local LLM (Ollama)** | Would need separate provider | Future enhancement | [ ] |
| P4-3 | **Function calling** | Structured output vs regex parsing | Consider for v2 | [ ] |

## API Key Requirements

You need valid API keys for live integration testing.

### Setup

```bash
# Copy the template and add your keys
cp .env.example .env

# Edit .env with your actual keys:
# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
```

> **WARNING: Shell Environment Behavior**
>
> Tests use `os.getenv()` which reads from BOTH your shell environment AND `.env` file.
> If you have API keys exported in `~/.zshrc` or `~/.bashrc`, live tests will run
> automatically even without a `.env` file. Use `-m mock` to skip live tests.

**Cost estimate for full live test run:** ~$0.50-2.00 (mostly from image tokens)

### Test Modes

| Mode | Command | API Calls | Cost |
|------|---------|-----------|------|
| Mock only | `pytest -m mock` | None | Free |
| All tests | `pytest` | If keys set | ~$0.50-2.00 |
| Live only | `pytest -m live` | Yes | ~$0.50-2.00 |

## Running Integration Tests

```bash
# RECOMMENDED: Run mock tests (safe, no API calls, no cost)
uv run pytest tests/integration/llm/ -v -m "mock"

# Run ALL tests (live tests run if keys are set)
uv run pytest tests/integration/llm/ -v --tb=long

# Run ONLY live API tests (opt-in, costs money)
uv run pytest tests/integration/llm/test_p0_critical.py -v -m "live"
```

### Mock Mode for CI/CD

For CI/CD or cost-sensitive testing, use `respx` to mock HTTP calls:

```python
import respx

@respx.mock
def test_openai_generate():
    respx.post("https://api.openai.com/v1/responses").respond(
        json={"output_text": '{"reasoning": "...", "action": {...}}'}
    )
    # ... test code
```

## Sign-Off Criteria

**Proceed to Spec-09 when:**

- [x] All P0 tests pass with BOTH OpenAI and Anthropic (2025-12-20)
- [x] All P1 tests pass (or have documented workarounds) (2025-12-20)
- [x] P2 tests reviewed (failures documented as known limitations) (2025-12-20)
- [x] At least ONE real API call made to each provider (2025-12-20)
- [x] Cost tracking verified accurate (2025-12-20)
- [x] Rate limit handling verified (2025-12-20)
- [x] Trajectory JSON serialization works end-to-end (2025-12-20)
- [x] Integration test file committed to `tests/integration/llm/` (2025-12-20)

## Discovered Issues Log

Document any issues found during integration testing:

| Date | ID | Severity | Description | Resolution |
|------|-----|----------|-------------|------------|
| 2025-12-20 | - | - | No issues found | 61 mock + 2 live tests passed |

## Pre-Flight Check for Spec-09

Before starting Spec-09, verify:

1. **WSI Pipeline (Spec-05.5)**: Can open slide, get thumbnail, crop regions
2. **LLM Pipeline (this checkpoint)**: Can send messages, parse responses, track context
3. **Both pipelines tested independently with real data/APIs**
4. **Cost estimation working** — you'll burn money fast in the agent loop

## Notes

- This checkpoint should take 2-4 hours for thorough testing
- Budget ~$2-5 for API calls during integration testing
- Do NOT skip rate limit testing — it WILL happen in production
- If you find P0/P1 issues, fix them before proceeding to Spec-09
- The agent loop (Spec-09) amplifies every bug — find them now
