# Spec-06: LLM Provider Abstraction

## Overview
This specification defines the abstraction layer for Large Multimodal Models (LMMs). It decouples the core agent logic from specific API implementations (OpenAI, Anthropic). It handles the complexity of constructing multimodal messages, managing rate limits, tracking costs, and robustly parsing structured outputs (reasoning + bounding box) from the models.

## Dependencies
- [Spec-01: Project Foundation & Tooling](./spec-01-foundation.md)
- [Spec-03: Coordinate System & Geometry](./spec-03-coordinates.md)

## Acceptance Criteria
- [ ] `LLMProvider` Protocol defined.
- [ ] `OpenAIProvider` implemented (supporting GPT-4o, GPT-5).
- [ ] `AnthropicProvider` implemented (supporting Claude 4.5-Sonnet per paper; model name configurable).
- [ ] Support for multimodal inputs (text + base64 images).
- [ ] Robust parsing of `StepResponse` (reasoning text + action).
- [ ] Automatic retry logic for API errors and rate limits (using `tenacity`).
- [ ] Cost tracking per request.

## Technical Design

### Data Models

```python
from pydantic import BaseModel, Field
from typing import Literal, Union, List

class BoundingBoxAction(BaseModel):
    action_type: Literal["crop"] = "crop"
    x: int
    y: int
    width: int
    height: int

class FinalAnswerAction(BaseModel):
    action_type: Literal["answer"] = "answer"
    answer_text: str

class StepResponse(BaseModel):
    reasoning: str
    action: Union[BoundingBoxAction, FinalAnswerAction]

class MessageContent(BaseModel):
    type: Literal["text", "image"]
    text: str | None = None
    image_base64: str | None = None
    media_type: str = "image/jpeg"

class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: List[MessageContent]

class TokenUsage(BaseModel):
    """Track token usage and cost per API call."""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float

class LLMResponse(BaseModel):
    """Full response including parsed output and metadata."""
    step_response: StepResponse
    usage: TokenUsage
    model: str
    latency_ms: float
```

### Interfaces

```python
from typing import Protocol

class LLMProvider(Protocol):
    async def generate_response(self, messages: List[Message]) -> LLMResponse: ...
    def get_model_name(self) -> str: ...
    def get_target_size(self) -> int: ...  # 1000 for OpenAI, 500 for Anthropic
```

### Cost Calculation

Token costs vary by model and image tokens. Maintain a lookup table:

```python
# src/giant/llm/pricing.py
PRICING_USD_PER_1K = {
    "gpt-5": {"input": 0.01, "output": 0.03, "image_base": 0.00255},
    "gpt-4o": {"input": 0.005, "output": 0.015, "image_base": 0.00255},
    # Paper model label: "Claude 4.5-Sonnet" (model name is configurable; keep pricing table keys aligned to configured names)
    "claude-4-5-sonnet": {"input": 0.003, "output": 0.015, "image_per_1k_px": 0.00048},
}

def calculate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    prices = PRICING_USD_PER_1K.get(model, {"input": 0.01, "output": 0.03})
    return (prompt_tokens * prices["input"] + completion_tokens * prices["output"]) / 1000
```

**Note:** Image token costs are approximations. Update pricing table as APIs evolve.

### Implementation Details

#### Structured Output Strategy
To ensure reliability and consistent parsing (reasoning + action), use provider-native structured output where available.

1.  **OpenAI (SDK v2.x):** Use the Responses API with a JSON Schema `response_format`, then parse into `StepResponse`.
    - Request: `client.responses.create(model=..., input=[...], response_format={"type": "json_schema", "json_schema": {"name": "StepResponse", "schema": StepResponse.model_json_schema()}})`
    - Parse: `StepResponse.model_validate_json(response.output_text)`
2.  **Anthropic:** Use Tool Use. Define a tool `submit_step` that takes `reasoning` and `action` arguments. Force the model to use this tool (`tool_choice={"type": "tool", "name": "submit_step"}`).

#### Image Resolution Handling
Per the paper, different providers may require different image resolutions due to cost/performance trade-offs.
- `OpenAIProvider._get_target_size()` -> `settings.IMAGE_SIZE_OPENAI` (1000px)
- `AnthropicProvider._get_target_size()` -> `settings.IMAGE_SIZE_ANTHROPIC` (500px)

#### Rate Limiting & Retries
**Retries:** Use `tenacity` decorator:
```python
@retry(
    wait=wait_random_exponential(min=1, max=60),
    stop=stop_after_attempt(6),
    retry=retry_if_exception_type((RateLimitError, APIConnectionError))
)
```

**Rate limiting (must-have for benchmarks):** Use `aiolimiter.AsyncLimiter` in each provider to cap request throughput and avoid cascading 429s.
```python
from aiolimiter import AsyncLimiter

class OpenAIProvider:
    def __init__(..., rpm: int = 60):
        self._limiter = AsyncLimiter(max_rate=rpm, time_period=60)

    async def generate_response(...):
        async with self._limiter:
            return await self._call_openai(...)
```

#### Circuit Breaker (Failure Containment)
Add a small circuit breaker around API calls:
- Open the circuit after `N` consecutive failures (e.g., 10).
- While open, fail fast for `cooldown_seconds` (e.g., 60) to protect budgets and provider limits.
- Transition to half-open and allow a limited number of trial calls to close the circuit on success.

#### Provider Factory + Fallback
Implement a `ProviderFactory` that creates providers from `Settings` (Dependency Inversion):
- `ProviderFactory.create(provider: Literal["openai","anthropic"], model: str) -> LLMProvider`
- Optional `FallbackProvider(primary, fallbacks)` that retries on **retriable** exceptions by switching providers/models.

#### Message Construction
- **OpenAI (Responses API):** Maps to `{"type": "input_image", "image_url": f"data:image/jpeg;base64,{b64}"}` plus `{"type": "input_text", "text": ...}`.
- **Anthropic:** Maps to `{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}}`.

## Test Plan

### Unit Tests
1.  **Message Formatting:** Verify `Message` objects are correctly converted to provider-specific JSON payloads.
2.  **Parsing:** Mock raw API responses (JSON strings) and verify they parse into `StepResponse` objects.
3.  **Error Handling:** Mock API errors and verify `tenacity` retry logic (using `wait=0` for tests).

### Integration Tests
- **Live API Test:** (Marked `@pytest.mark.cost`) A test that actually calls the API with a small dummy image to verify auth and schema alignment.

## File Structure
```text
src/giant/llm/
├── __init__.py
├── protocol.py       # LLMProvider, Message, StepResponse, TokenUsage
├── pricing.py        # Cost calculation per model
├── openai_client.py
├── anthropic_client.py
└── converters.py     # Helpers for message format conversion
tests/unit/llm/
├── test_openai.py
├── test_anthropic.py
└── test_pricing.py
```
