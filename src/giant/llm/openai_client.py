"""OpenAI LLM Provider implementation for GIANT.

This module implements the LLMProvider protocol for OpenAI models (GPT-4o, GPT-5).
It uses the OpenAI Responses API with structured output (JSON schema) for
reliable parsing of StepResponse.

Per Spec-06:
- Uses response_format with JSON schema for structured output
- Implements rate limiting via aiolimiter
- Implements retry logic via tenacity
- Tracks token usage and cost
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

from aiolimiter import AsyncLimiter
from openai import APIConnectionError, AsyncOpenAI, RateLimitError
from pydantic import ValidationError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from giant.config import Settings, settings
from giant.llm.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from giant.llm.converters import (
    count_images_in_messages,
    get_system_prompt_for_openai,
    messages_to_openai_input,
)
from giant.llm.pricing import calculate_cost, calculate_image_cost_openai
from giant.llm.protocol import (
    LLMError,
    LLMParseError,
    LLMResponse,
    Message,
    StepResponse,
    TokenUsage,
)
from giant.llm.schemas import step_response_json_schema

logger = logging.getLogger(__name__)


def _build_json_schema() -> dict[str, Any]:
    """Build JSON schema for StepResponse structured output.

    Returns:
        OpenAI-compatible JSON schema dictionary.
    """
    return {
        "name": "StepResponse",
        "strict": True,
        "schema": step_response_json_schema(),
    }


@dataclass
class OpenAIProvider:
    """OpenAI LLM provider implementation.

    Uses the Responses API with JSON schema for structured output.
    Implements rate limiting, retry logic, and circuit breaker.

    Usage:
        provider = OpenAIProvider()
        response = await provider.generate_response(messages)
    """

    model: str = "gpt-5.2-pro-2025-12-11"
    settings: Settings = field(default_factory=lambda: settings)

    # Internal state (initialized in __post_init__)
    _client: AsyncOpenAI = field(init=False, repr=False)
    _limiter: AsyncLimiter = field(init=False, repr=False)
    _circuit_breaker: CircuitBreaker[Any] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Initialize the OpenAI client and rate limiter."""
        api_key = self.settings.require_openai_key()
        self._client = AsyncOpenAI(api_key=api_key)
        self._limiter = AsyncLimiter(
            max_rate=self.settings.OPENAI_RPM,
            time_period=60,
        )
        self._circuit_breaker = CircuitBreaker(
            provider_name="openai",
            config=CircuitBreakerConfig(
                failure_threshold=10,
                cooldown_seconds=60.0,
            ),
        )

    def get_model_name(self) -> str:
        """Get the model identifier."""
        return self.model

    def get_target_size(self) -> int:
        """Get the target image size for OpenAI (1000px per paper)."""
        return self.settings.IMAGE_SIZE_OPENAI

    async def generate_response(self, messages: list[Message]) -> LLMResponse:
        """Generate a response from OpenAI.

        Args:
            messages: Conversation history.

        Returns:
            LLMResponse with parsed StepResponse and metadata.

        Raises:
            LLMError: If API call fails after retries.
            LLMParseError: If response cannot be parsed.
            CircuitBreakerOpenError: If circuit is open.
        """
        self._circuit_breaker.check()

        try:
            async with self._limiter:
                return await self._call_with_retry(messages)
        except LLMParseError:
            # Schema/prompt mismatch: don't treat as provider outage.
            raise
        except (RateLimitError, APIConnectionError) as e:
            self._circuit_breaker.record_failure()
            raise LLMError(
                f"OpenAI API call failed after retries: {e}",
                provider="openai",
                model=self.model,
                cause=e,
            ) from e
        except Exception:
            self._circuit_breaker.record_failure()
            raise

    @retry(
        wait=wait_random_exponential(min=1, max=60),
        stop=stop_after_attempt(6),
        retry=retry_if_exception_type((RateLimitError, APIConnectionError)),
        reraise=True,
    )
    async def _call_with_retry(self, messages: list[Message]) -> LLMResponse:
        """Make API call with retry logic.

        Args:
            messages: Conversation history.

        Returns:
            LLMResponse with parsed output.
        """
        start_time = time.perf_counter()

        try:
            # Build request
            system_prompt = get_system_prompt_for_openai(messages)
            input_messages = messages_to_openai_input(messages)

            # Make API call using responses.create for structured output
            response = await self._client.responses.create(  # type: ignore[call-overload]
                model=self.model,
                input=input_messages,
                instructions=system_prompt,
                text={
                    "format": {
                        "type": "json_schema",
                        "json_schema": _build_json_schema(),
                    }
                },
            )

            latency_ms = (time.perf_counter() - start_time) * 1000

            # Parse response
            output_text = response.output_text
            if output_text is None:
                raise LLMParseError(
                    "No output text in response",
                    provider="openai",
                    model=self.model,
                )

            try:
                step_response = StepResponse.model_validate_json(output_text)
            except ValidationError as e:
                raise LLMParseError(
                    f"Failed to parse StepResponse: {e}",
                    raw_output=output_text,
                    provider="openai",
                    model=self.model,
                ) from e

            # Calculate usage and cost
            usage = response.usage
            prompt_tokens = usage.input_tokens if usage else 0
            completion_tokens = usage.output_tokens if usage else 0
            total_tokens = prompt_tokens + completion_tokens

            # Calculate cost (text + images)
            text_cost = calculate_cost(self.model, prompt_tokens, completion_tokens)
            image_count = count_images_in_messages(messages)
            image_cost = calculate_image_cost_openai(self.model, image_count)
            total_cost = text_cost + image_cost

            token_usage = TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                cost_usd=total_cost,
            )

            self._circuit_breaker.record_success()

            return LLMResponse(
                step_response=step_response,
                usage=token_usage,
                model=self.model,
                latency_ms=latency_ms,
            )

        except (RateLimitError, APIConnectionError):
            # Let tenacity handle retries
            raise
        except LLMParseError:
            # Don't wrap parse errors
            raise
        except Exception as e:
            raise LLMError(
                f"OpenAI API call failed: {e}",
                provider="openai",
                model=self.model,
                cause=e,
            ) from e
