"""LLM Provider abstraction for GIANT.

This package provides the abstraction layer for Large Multimodal Models (LMMs).
It decouples the core agent logic from specific API implementations.

Public API:
    - Protocol & Data Models: LLMProvider, Message, StepResponse, etc.
    - Providers: OpenAIProvider, AnthropicProvider
    - Factory: create_provider()
    - Exceptions: LLMError, LLMParseError, CircuitBreakerOpenError

Usage:
    from giant.llm import create_provider, Message, MessageContent

    provider = create_provider("openai", model="gpt-4o")
    response = await provider.generate_response(messages)
"""

from giant.llm.anthropic_client import AnthropicProvider
from giant.llm.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitState
from giant.llm.openai_client import OpenAIProvider
from giant.llm.pricing import (
    PRICING_USD_PER_1K,
    calculate_cost,
    calculate_image_cost_anthropic,
    calculate_image_cost_openai,
    calculate_total_cost,
    get_model_pricing,
)
from giant.llm.protocol import (
    Action,
    BoundingBoxAction,
    CircuitBreakerOpenError,
    FinalAnswerAction,
    LLMError,
    LLMParseError,
    LLMProvider,
    LLMResponse,
    Message,
    MessageContent,
    StepResponse,
    TokenUsage,
)

__all__ = [
    "PRICING_USD_PER_1K",
    "Action",
    "AnthropicProvider",
    "BoundingBoxAction",
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerOpenError",
    "CircuitState",
    "FinalAnswerAction",
    "LLMError",
    "LLMParseError",
    "LLMProvider",
    "LLMResponse",
    "Message",
    "MessageContent",
    "OpenAIProvider",
    "StepResponse",
    "TokenUsage",
    "calculate_cost",
    "calculate_image_cost_anthropic",
    "calculate_image_cost_openai",
    "calculate_total_cost",
    "create_provider",
    "get_model_pricing",
]


def create_provider(
    provider: str,
    *,
    model: str | None = None,
) -> LLMProvider:
    """Factory function to create LLM providers.

    Args:
        provider: Provider name ("openai" or "anthropic").
        model: Optional model override. If not specified, uses provider defaults:
            - OpenAI: "gpt-4o"
            - Anthropic: "claude-sonnet-4-20250514"

    Returns:
        An LLMProvider instance.

    Raises:
        ValueError: If provider is unknown.

    Example:
        provider = create_provider("openai", model="gpt-4o")
        response = await provider.generate_response(messages)
    """
    if provider == "openai":
        return OpenAIProvider(model=model or "gpt-4o")
    elif provider == "anthropic":
        return AnthropicProvider(model=model or "claude-sonnet-4-20250514")
    else:
        raise ValueError(
            f"Unknown provider: {provider}. Supported providers: 'openai', 'anthropic'"
        )
