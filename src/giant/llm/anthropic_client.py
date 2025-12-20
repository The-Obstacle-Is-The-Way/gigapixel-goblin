"""Anthropic LLM Provider implementation for GIANT.

This module implements the LLMProvider protocol for Anthropic models
(Claude). It uses Tool Use with forced tool choice
for structured output.

Per Spec-06:
- Uses tool_choice to force use of submit_step tool
- Implements rate limiting via aiolimiter
- Implements retry logic via tenacity
- Tracks token usage and cost
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

from aiolimiter import AsyncLimiter
from anthropic import APIConnectionError, AsyncAnthropic, RateLimitError
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
    count_image_pixels_in_messages,
    get_system_prompt_for_anthropic,
    messages_to_anthropic,
)
from giant.llm.model_registry import DEFAULT_ANTHROPIC_MODEL, validate_model_id
from giant.llm.pricing import calculate_cost, calculate_image_cost_anthropic
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


def _build_submit_step_tool() -> dict[str, Any]:
    """Build the submit_step tool definition for Anthropic.

    Returns:
        Tool definition dictionary for the Anthropic API.
    """
    return {
        "name": "submit_step",
        "description": (
            "Submit your reasoning and action for this navigation step. "
            "You MUST call this tool to provide your response."
        ),
        "input_schema": step_response_json_schema(),
    }


def _parse_tool_use_to_step_response(tool_input: dict[str, Any]) -> StepResponse:
    """Parse tool use input into StepResponse.

    Handles the case where Anthropic returns nested fields as JSON strings
    instead of parsed dicts (common with complex tool schemas).

    Args:
        tool_input: The input dictionary from the tool use.

    Returns:
        Parsed StepResponse.

    Raises:
        LLMParseError: If parsing fails.
    """
    try:
        # Handle case where 'action' is returned as a JSON string instead of dict
        # This can happen with complex nested schemas in tool use
        if isinstance(tool_input.get("action"), str):
            try:
                tool_input = {
                    **tool_input,
                    "action": json.loads(tool_input["action"]),
                }
            except json.JSONDecodeError:
                pass  # Let pydantic handle the validation error

        return StepResponse.model_validate(tool_input)
    except ValidationError as e:
        raise LLMParseError(
            f"Failed to parse StepResponse: {e}",
            raw_output=str(tool_input),
            provider="anthropic",
        ) from e


@dataclass
class AnthropicProvider:
    """Anthropic LLM provider implementation.

    Uses Tool Use with forced tool choice for structured output.
    Implements rate limiting, retry logic, and circuit breaker.

    Usage:
        provider = AnthropicProvider()
        response = await provider.generate_response(messages)
    """

    model: str = DEFAULT_ANTHROPIC_MODEL
    settings: Settings = field(default_factory=lambda: settings)

    # Internal state
    _client: AsyncAnthropic = field(init=False, repr=False)
    _limiter: AsyncLimiter = field(init=False, repr=False)
    _circuit_breaker: CircuitBreaker[Any] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Initialize the Anthropic client and rate limiter."""
        validate_model_id(self.model, provider="anthropic")
        api_key = self.settings.require_anthropic_key()
        self._client = AsyncAnthropic(api_key=api_key)
        self._limiter = AsyncLimiter(
            max_rate=self.settings.ANTHROPIC_RPM,
            time_period=60,
        )
        self._circuit_breaker = CircuitBreaker(
            provider_name="anthropic",
            config=CircuitBreakerConfig(
                failure_threshold=10,
                cooldown_seconds=60.0,
            ),
        )

    def get_model_name(self) -> str:
        """Get the model identifier."""
        return self.model

    def get_target_size(self) -> int:
        """Get the target image size for Anthropic (500px per paper)."""
        return self.settings.IMAGE_SIZE_ANTHROPIC

    async def generate_response(self, messages: list[Message]) -> LLMResponse:
        """Generate a response from Anthropic.

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
                f"Anthropic API call failed after retries: {e}",
                provider="anthropic",
                model=self.model,
                cause=e,
            ) from e
        # Note: Other exceptions (application bugs, validation errors, etc.)
        # propagate without tripping circuit breaker - only transient/remote
        # errors should affect circuit breaker state.

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
            system_prompt = get_system_prompt_for_anthropic(messages)
            anthropic_messages = messages_to_anthropic(messages)

            # Make API call with forced tool use
            response = await self._client.messages.create(  # type: ignore[call-overload]
                model=self.model,
                max_tokens=4096,
                system=system_prompt or "",
                messages=anthropic_messages,
                tools=[_build_submit_step_tool()],
                tool_choice={"type": "tool", "name": "submit_step"},
            )

            latency_ms = (time.perf_counter() - start_time) * 1000

            # Find tool use in response
            tool_use_block = None
            for block in response.content:
                if block.type == "tool_use" and block.name == "submit_step":
                    tool_use_block = block
                    break

            if tool_use_block is None:
                raise LLMParseError(
                    "No submit_step tool use in response",
                    raw_output=str(response.content),
                    provider="anthropic",
                    model=self.model,
                )

            step_response = _parse_tool_use_to_step_response(tool_use_block.input)

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

            text_cost = calculate_cost(self.model, prompt_tokens, completion_tokens)
            image_pixels = count_image_pixels_in_messages(messages)
            image_cost = calculate_image_cost_anthropic(self.model, image_pixels)
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
        except LLMError:
            # Don't wrap already-wrapped LLM errors
            raise
        except Exception as e:
            raise LLMError(
                f"Anthropic API call failed: {e}",
                provider="anthropic",
                model=self.model,
                cause=e,
            ) from e
