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
    "claude-3-5-sonnet-20241022": {"input": 0.003, "output": 0.015, "image_per_1k_px": 0.00048},
}

def calculate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    prices = PRICING_USD_PER_1K.get(model, {"input": 0.01, "output": 0.03})
    return (prompt_tokens * prices["input"] + completion_tokens * prices["output"]) / 1000
```

**Note:** Image token costs are approximations. Update pricing table as APIs evolve.

### Implementation Details

#### Structured Output Strategy
To ensure reliability and Chain-of-Thought (CoT) reasoning:

1.  **OpenAI:** Use `client.beta.chat.completions.parse` with `response_format=StepResponse`. This enforces the schema and allows the model to output reasoning field first.
2.  **Anthropic:** Use Tool Use. Define a tool `submit_step` that takes `reasoning` and `action` arguments. Force the model to use this tool (`tool_choice={"type": "tool", "name": "submit_step"}`).

#### Image Resolution Handling
Per the paper, different providers may require different image resolutions due to cost/performance trade-offs.
- `OpenAIProvider._get_target_size()` -> `settings.IMAGE_SIZE_OPENAI` (1000px)
- `AnthropicProvider._get_target_size()` -> `settings.IMAGE_SIZE_ANTHROPIC` (500px)

#### Rate Limiting & Retries
Use `tenacity` decorator:
```python
@retry(
    wait=wait_random_exponential(min=1, max=60),
    stop=stop_after_attempt(6),
    retry=retry_if_exception_type((RateLimitError, APIConnectionError))
)
```

#### Message Construction
- **OpenAI:** Maps `MessageContent` to `{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}`.
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
