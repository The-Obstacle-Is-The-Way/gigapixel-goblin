# LLM Integration

GIANT uses large multimodal models (LMMs) to analyze images and decide navigation actions. This page explains how LLM providers are integrated.

## Provider Architecture

GIANT abstracts LLM interactions behind a protocol interface:

```python
class LLMProvider(Protocol):
    async def generate_response(self, messages: list[Message]) -> LLMResponse:
        """Generate a response from the LLM."""
        ...

    def get_model_name(self) -> str:
        """Get the model identifier."""
        ...

    def get_target_size(self) -> int:
        """Get optimal image size for this provider."""
        ...
```

This allows swapping providers without changing agent code.

## Supported Providers

### OpenAI

Uses the **Responses API** with structured outputs:

```python
from giant.llm import create_provider

provider = create_provider("openai", model="gpt-5.2")
```

**Features:**
- Native JSON schema enforcement via `response_format`
- Image handling via base64 data URLs
- Token and cost tracking from response metadata

**Target Size:** 1000px (higher resolution for detail)

### Anthropic

Uses the **Messages API** with tool use:

```python
provider = create_provider("anthropic", model="claude-sonnet-4-5-20250929")
```

**Features:**
- Tool use for structured output (`submit_step` tool)
- Image handling via base64 content blocks
- Token and cost tracking from response metadata

**Target Size:** 500px (cost-optimized)

## Message Format

Internally, GIANT uses a unified message format:

```python
from pydantic import BaseModel
from typing import Literal

class MessageContent(BaseModel):
    type: Literal["text", "image"]
    text: str | None = None
    image_base64: str | None = None
    media_type: str = "image/jpeg"

class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: list[MessageContent]
```

Converters translate to provider-specific formats:

```python
# OpenAI format
{
    "role": "user",
    "content": [
        {"type": "input_text", "text": "Analyze this image..."},
        {"type": "input_image", "image_url": "data:image/jpeg;base64,..."}
    ]
}

# Anthropic format
{
    "role": "user",
    "content": [
        {"type": "text", "text": "Analyze this image..."},
        {"type": "image", "source": {"type": "base64", "data": "...", "media_type": "image/jpeg"}}
    ]
}
```

## Structured Output

GIANT requires structured JSON responses:

```python
class StepResponse(BaseModel):
    reasoning: str
    action: BoundingBoxAction | FinalAnswerAction

class BoundingBoxAction(BaseModel):
    action_type: Literal["crop"] = "crop"
    x: int
    y: int
    width: int
    height: int

class FinalAnswerAction(BaseModel):
    action_type: Literal["answer"] = "answer"
    answer_text: str
```

### OpenAI: JSON Schema

```python
response = client.responses.create(
    model="gpt-5.2",
    input=messages,
    text={
        "format": {
            "type": "json_schema",
            "name": "step_response",
            "schema": StepResponse.model_json_schema(),
        }
    }
)
```

### Anthropic: Tool Use

```python
response = client.messages.create(
    model="claude-sonnet-4-5-20250929",
    messages=messages,
    tools=[{
        "name": "submit_step",
        "description": "Provide your response",
        "input_schema": StepResponse.model_json_schema(),
    }],
    tool_choice={"type": "tool", "name": "submit_step"},
)
```

## Model Registry

Only approved models are allowed:

| Provider | Model ID | Status |
|----------|----------|--------|
| OpenAI | `gpt-5.2` | Default |
| Anthropic | `claude-sonnet-4-5-20250929` | Supported |
| Google | `gemini-3-pro-preview` | Reserved (provider not yet implemented) |

Models are validated at runtime:

```python
from giant.llm.model_registry import validate_model_id

validate_model_id("gpt-5.2")  # OK
validate_model_id("gpt-4o")   # Raises ValueError
```

See [Model Registry](../models/model-registry.md) for details.

## Cost Tracking

Each response includes usage and cost:

```python
@dataclass
class TokenUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float
```

Costs are calculated using pricing tables:

```python
# Example pricing (per 1M tokens)
PRICING = {
    "gpt-5.2": {"input": 1.75, "output": 14.00},
    "claude-sonnet-4-5-20250929": {"input": 3.00, "output": 15.00},
    "gemini-3-pro-preview": {"input": 2.00, "output": 12.00},
}
```

## Error Handling

### LLMError

Base exception for API failures:

```python
class LLMError(Exception):
    """Raised when API calls fail after retries."""
    provider: str | None
    model: str | None
    cause: Exception | None
```

### LLMParseError

When response can't be parsed:

```python
class LLMParseError(LLMError):
    """Raised when output doesn't match expected schema."""
    raw_output: str | None
```

### Circuit Breaker

Protects against cascading failures:

```python
class CircuitBreakerOpenError(LLMError):
    """Raised when too many consecutive failures occur."""
    cooldown_remaining_seconds: float
```

## Configuration

### Environment Variables

```bash
# Required for respective providers
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

### Provider-Specific Settings

| Provider | Target Size | Notes |
|----------|-------------|-------|
| OpenAI | 1000px | Higher resolution, higher cost |
| Anthropic | 500px | Cost-optimized, still effective |

## Adding New Providers

To add a new LLM provider:

1. Create client class implementing `LLMProvider` protocol
2. Add converter functions for message format
3. Add to `create_provider()` factory
4. Add model to registry with pricing
5. Add tests

Example skeleton:

```python
class NewProvider:
    def __init__(self, model: str):
        validate_model_id(model, provider="newprovider")
        self.model = model
        self.client = NewProviderClient()

    async def generate_response(self, messages: list[Message]) -> LLMResponse:
        # Convert messages
        # Call API
        # Parse response
        # Return LLMResponse
        ...

    def get_model_name(self) -> str:
        return self.model

    def get_target_size(self) -> int:
        return 1000
```

## Next Steps

- [Prompt Design](../prompts/prompt-design.md) - Navigation prompts
- [Model Registry](../models/model-registry.md) - Approved models
- [Configuring Providers](../guides/configuring-providers.md) - Setup guide
