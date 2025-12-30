"""LLM Provider Protocol and data models for GIANT.

This module defines the core abstractions for interacting with Large Multimodal
Models (LMMs). It provides:

- Data models for messages, responses, and actions
- The LLMProvider Protocol that all providers must implement
- Type-safe interfaces for multimodal (text + image) communication

Per Spec-06, these abstractions decouple the agent logic from specific API
implementations (OpenAI, Anthropic).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Literal, Protocol

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    pass


# =============================================================================
# Action Models (what the LLM decides to do)
# =============================================================================


class BoundingBoxAction(BaseModel):
    """Action to crop a region from the current view.

    The bounding box coordinates are in **Level-0 (full-slide)** pixel space.
    The agent uses this to "zoom in" on a region of interest.
    """

    action_type: Literal["crop"] = "crop"
    x: int = Field(..., ge=0, description="Left edge of bounding box")
    y: int = Field(..., ge=0, description="Top edge of bounding box")
    width: int = Field(..., gt=0, description="Width of bounding box")
    height: int = Field(..., gt=0, description="Height of bounding box")


class FinalAnswerAction(BaseModel):
    """Action to provide the final answer and end navigation.

    The agent uses this when it has gathered enough information to answer
    the question or when it cannot proceed further.
    """

    action_type: Literal["answer"] = "answer"
    answer_text: str = Field(..., min_length=1, description="The final answer")


HypothesisText = Annotated[str, Field(min_length=1)]


class ConchAction(BaseModel):
    """Action to score hypotheses using CONCH (paper ablation feature).

    The agent supplies the *current* observation image (thumbnail or crop) along
    with a list of textual hypotheses to CONCH and receives similarity scores.
    """

    action_type: Literal["conch"] = "conch"
    hypotheses: list[HypothesisText] = Field(
        ...,
        min_length=1,
        description="Textual hypotheses to score against the current image",
    )


# Discriminated union for action types
Action = Annotated[
    BoundingBoxAction | FinalAnswerAction | ConchAction,
    Field(discriminator="action_type"),
]


# =============================================================================
# Response Models
# =============================================================================


class StepResponse(BaseModel):
    """Response from the LLM for a single navigation step.

    Contains the model's reasoning (chain-of-thought) and the action it
    decided to take. The reasoning is critical for interpretability and
    debugging the agent's decision process.
    """

    reasoning: str = Field(
        ...,
        min_length=1,
        description="Chain-of-thought reasoning for the action",
    )
    action: Action = Field(..., description="The action to take")


class TokenUsage(BaseModel):
    """Token usage and cost for an API call.

    Tracks prompt (input) and completion (output) tokens separately
    for accurate cost accounting.
    """

    prompt_tokens: int = Field(..., ge=0)
    completion_tokens: int = Field(..., ge=0)
    total_tokens: int = Field(..., ge=0)
    cost_usd: float = Field(..., ge=0.0)


class LLMResponse(BaseModel):
    """Full response from an LLM provider.

    Combines the parsed step response with metadata about the API call
    including token usage, cost, and latency.
    """

    step_response: StepResponse
    usage: TokenUsage
    model: str = Field(..., description="Model identifier used for this call")
    latency_ms: float = Field(..., ge=0.0, description="API call latency in ms")


# =============================================================================
# Message Models (input to the LLM)
# =============================================================================


class MessageContent(BaseModel):
    """A single piece of content within a message.

    Can be either text or an image. For images, the base64-encoded data
    and media type are provided.
    """

    type: Literal["text", "image"]
    text: str | None = None
    image_base64: str | None = None
    media_type: str = Field(
        default="image/jpeg",
        description="MIME type for image content",
    )


class Message(BaseModel):
    """A message in the conversation with the LLM.

    Messages can contain multiple content items (text and images).
    The role indicates who sent the message.
    """

    role: Literal["system", "user", "assistant"]
    content: list[MessageContent] = Field(..., min_length=1)


# =============================================================================
# LLM Provider Protocol
# =============================================================================


class LLMProvider(Protocol):
    """Protocol defining the interface for LLM providers.

    All LLM providers (OpenAI, Anthropic, etc.) must implement this
    interface to be used with the GIANT agent.

    The protocol is intentionally minimal to allow flexibility in
    implementation while ensuring consistent behavior.
    """

    async def generate_response(self, messages: list[Message]) -> LLMResponse:
        """Generate a response from the LLM.

        Args:
            messages: Conversation history including system prompt and
                user messages with text/image content.

        Returns:
            LLMResponse containing the parsed step response and metadata.

        Raises:
            LLMError: If the API call fails after retries.
            LLMParseError: If the response cannot be parsed into StepResponse.
        """
        ...

    def get_model_name(self) -> str:
        """Get the model identifier being used.

        Returns:
            Model identifier string (e.g., "gpt-5.2").
        """
        ...

    def get_target_size(self) -> int:
        """Get the target image size for this provider.

        Different providers have different optimal image sizes due to
        cost/performance trade-offs. Per the paper:
        - OpenAI: 1000px (higher resolution)
        - Anthropic: 500px (cost-optimized)

        Returns:
            Target long-side dimension in pixels.
        """
        ...


# =============================================================================
# Exceptions
# =============================================================================


class LLMError(Exception):
    """Base exception for LLM-related errors.

    Raised when API calls fail after retries or when providers
    encounter unrecoverable errors.
    """

    def __init__(
        self,
        message: str,
        *,
        provider: str | None = None,
        model: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        """Initialize LLM error.

        Args:
            message: Human-readable error description.
            provider: Provider name (e.g., "openai", "anthropic").
            model: Model identifier if known.
            cause: Original exception that caused this error.
        """
        self.provider = provider
        self.model = model
        self.cause = cause
        super().__init__(message)


class LLMParseError(LLMError):
    """Raised when LLM output cannot be parsed into expected format.

    This typically means the model returned malformed JSON or didn't
    follow the expected schema.
    """

    def __init__(
        self,
        message: str,
        *,
        raw_output: str | None = None,
        provider: str | None = None,
        model: str | None = None,
    ) -> None:
        """Initialize parse error.

        Args:
            message: Description of the parsing failure.
            raw_output: The raw output that failed to parse.
            provider: Provider name.
            model: Model identifier.
        """
        self.raw_output = raw_output
        super().__init__(message, provider=provider, model=model)


class CircuitBreakerOpenError(LLMError):
    """Raised when the circuit breaker is open.

    This means too many consecutive failures have occurred and the
    provider is temporarily unavailable to protect against cascading
    failures and budget overruns.
    """

    def __init__(
        self,
        message: str,
        *,
        cooldown_remaining_seconds: float,
        provider: str | None = None,
    ) -> None:
        """Initialize circuit breaker error.

        Args:
            message: Description of the circuit breaker state.
            cooldown_remaining_seconds: Time until circuit closes.
            provider: Provider name.
        """
        self.cooldown_remaining_seconds = cooldown_remaining_seconds
        super().__init__(message, provider=provider)
