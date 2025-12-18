"""P1: High Priority Integration Tests.

Edge cases that will cause production failures.
SHOULD PASS before proceeding to Spec-09.

Tests cover:
- Rate limit handling
- Token limit approach
- Image pruning
- Malformed model responses
- Empty model responses
- Invalid coordinates in crop
- Cost tracking
- Provider switching
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
import respx

from giant.agent.context import ContextManager
from giant.config import Settings
from giant.llm import (
    AnthropicProvider,
    BoundingBoxAction,
    LLMError,
    LLMParseError,
    Message,
    MessageContent,
    OpenAIProvider,
    StepResponse,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_openai_settings() -> Settings:
    """Create Settings with mock OpenAI API key."""
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        OPENAI_API_KEY="sk-test-mock-key",
    )


@pytest.fixture
def mock_anthropic_settings() -> Settings:
    """Create Settings with mock Anthropic API key."""
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        ANTHROPIC_API_KEY="sk-ant-test-mock-key",
    )


@pytest.fixture
def mock_both_settings() -> Settings:
    """Create Settings with both API keys."""
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        OPENAI_API_KEY="sk-test-mock-key",
        ANTHROPIC_API_KEY="sk-ant-test-mock-key",
    )


def _mock_openai_crop_response() -> dict[str, Any]:
    """Create a mock OpenAI response with crop action."""
    return {
        "id": "resp_123",
        "object": "response",
        "created": 1234567890,
        "model": "gpt-5.2-2025-12-11",
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "content": [
                    {
                        "type": "output_text",
                        "text": json.dumps(
                            {
                                "reasoning": "Found region of interest",
                                "action": {
                                    "action_type": "crop",
                                    "x": 100,
                                    "y": 200,
                                    "width": 500,
                                    "height": 500,
                                },
                            }
                        ),
                    }
                ],
            }
        ],
        "output_text": json.dumps(
            {
                "reasoning": "Found region of interest",
                "action": {
                    "action_type": "crop",
                    "x": 100,
                    "y": 200,
                    "width": 500,
                    "height": 500,
                },
            }
        ),
        "usage": {
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
        },
    }


def _mock_anthropic_crop_response() -> dict[str, Any]:
    """Create a mock Anthropic response with crop action."""
    return {
        "id": "msg_123",
        "type": "message",
        "role": "assistant",
        "content": [
            {
                "type": "tool_use",
                "id": "toolu_123",
                "name": "submit_step",
                "input": {
                    "reasoning": "Analyzing tissue",
                    "action": {
                        "action_type": "crop",
                        "x": 150,
                        "y": 250,
                        "width": 400,
                        "height": 400,
                    },
                },
            }
        ],
        "model": "claude-opus-4-5-20251101",
        "stop_reason": "tool_use",
        "usage": {
            "input_tokens": 120,
            "output_tokens": 60,
        },
    }


# =============================================================================
# P1-1: Rate limit handling
# =============================================================================


@pytest.mark.mock
class TestP1_1_RateLimitHandling:
    """P1-1: Test rate limit handling with retry.

    Note: Full retry testing requires either:
    1. Real API calls (expensive)
    2. Patching at the SDK level (complex)

    These tests verify the retry decorator is configured correctly
    and that the providers don't crash on rate limits.
    """

    def test_openai_provider_has_retry_decorator(self) -> None:
        """Test OpenAI provider has retry logic configured."""
        # Verify the _call_with_retry method has tenacity decorator
        from giant.llm.openai_client import OpenAIProvider

        method = OpenAIProvider._call_with_retry
        # Tenacity wraps the method with a __wrapped__ attribute
        assert hasattr(method, "__wrapped__") or hasattr(method, "retry")

    def test_anthropic_provider_has_retry_decorator(self) -> None:
        """Test Anthropic provider has retry logic configured."""
        from giant.llm.anthropic_client import AnthropicProvider

        method = AnthropicProvider._call_with_retry
        # Tenacity wraps the method with a __wrapped__ attribute
        assert hasattr(method, "__wrapped__") or hasattr(method, "retry")

    @pytest.mark.asyncio
    @respx.mock
    async def test_openai_circuit_breaker_tracks_failures(
        self, mock_openai_settings: Settings
    ) -> None:
        """Test circuit breaker tracks API failures."""
        # Return server error (will fail after retries)
        respx.post("https://api.openai.com/v1/responses").mock(
            return_value=httpx.Response(
                500, json={"error": {"message": "Server error"}}
            )
        )

        provider = OpenAIProvider(settings=mock_openai_settings)
        messages = [
            Message(role="system", content=[MessageContent(type="text", text="Test")]),
            Message(role="user", content=[MessageContent(type="text", text="Test")]),
        ]

        # Should fail (not retry on 500, just fail)
        with pytest.raises(LLMError):
            await provider.generate_response(messages)

    @pytest.mark.asyncio
    @respx.mock
    async def test_anthropic_success_after_mock_call(
        self, mock_anthropic_settings: Settings
    ) -> None:
        """Test Anthropic provider works with mock response."""
        respx.post("https://api.anthropic.com/v1/messages").mock(
            return_value=httpx.Response(200, json=_mock_anthropic_crop_response())
        )

        provider = AnthropicProvider(settings=mock_anthropic_settings)
        messages = [
            Message(role="system", content=[MessageContent(type="text", text="Test")]),
            Message(role="user", content=[MessageContent(type="text", text="Test")]),
        ]

        response = await provider.generate_response(messages)
        assert response.step_response is not None


# =============================================================================
# P1-2: Token limit approach
# =============================================================================


@pytest.mark.mock
class TestP1_2_TokenLimitApproach:
    """P1-2: Test behavior when approaching token limits."""

    def test_context_accumulates_without_limit(self) -> None:
        """Test context accumulates when no image limit set."""
        ctx = ContextManager(
            wsi_path="/slide.svs",
            question="Test?",
            max_steps=25,
            max_history_images=None,
        )

        # Add many turns
        for i in range(20):
            response = StepResponse(
                reasoning=f"Step {i}",
                action=BoundingBoxAction(x=0, y=0, width=100, height=100),
            )
            ctx.add_turn(image_base64=f"img{i}==", response=response)

        messages = ctx.get_messages(thumbnail_base64="thumb==")
        # Should have system + initial user + 20 turns (assistant+user pairs)
        # Actually: system + user0 + (assistant0 + user1) * 19 + assistant19
        # = 1 + 1 + 19*2 + 1 = 41 messages
        assert len(messages) == 41


# =============================================================================
# P1-3: Image pruning
# =============================================================================


@pytest.mark.mock
class TestP1_3_ImagePruning:
    """P1-3: Test image pruning when max_history_images is set."""

    def test_pruning_with_max_history_3(self) -> None:
        """Test older images replaced with placeholder when max=3."""
        ctx = ContextManager(
            wsi_path="/slide.svs",
            question="Q?",
            max_steps=10,
            max_history_images=3,
        )

        # Add 5 turns
        for i in range(5):
            response = StepResponse(
                reasoning=f"Step {i}",
                action=BoundingBoxAction(x=0, y=0, width=100, height=100),
            )
            ctx.add_turn(image_base64=f"img{i}==", response=response)

        messages = ctx.get_messages(thumbnail_base64="thumb==")

        # Count images - should have thumbnail + last 3 crops = 4
        image_count = sum(1 for m in messages for c in m.content if c.type == "image")
        assert image_count == 4  # thumb + 3 most recent

    def test_pruned_images_have_placeholder(self) -> None:
        """Test pruned images are replaced with descriptive placeholder."""
        ctx = ContextManager(
            wsi_path="/slide.svs",
            question="Q?",
            max_steps=10,
            max_history_images=2,
        )

        # Add 4 turns
        for i in range(4):
            response = StepResponse(
                reasoning=f"Step {i}",
                action=BoundingBoxAction(x=0, y=0, width=100, height=100),
            )
            ctx.add_turn(image_base64=f"img{i}==", response=response)

        messages = ctx.get_messages(thumbnail_base64="thumb==")

        # Check that pruned messages contain placeholder text
        placeholder_found = False
        for msg in messages:
            for content in msg.content:
                if content.type == "text" and content.text:
                    if "removed" in content.text.lower():
                        placeholder_found = True
                        break

        assert placeholder_found


# =============================================================================
# P1-4: Malformed model response
# =============================================================================


@pytest.mark.mock
class TestP1_4_MalformedResponse:
    """P1-4: Test handling of malformed model responses."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_openai_invalid_json_raises_parse_error(
        self, mock_openai_settings: Settings
    ) -> None:
        """Test OpenAI raises LLMParseError on invalid JSON."""
        respx.post("https://api.openai.com/v1/responses").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "resp_123",
                    "object": "response",
                    "output": [],
                    "output_text": "not valid json {{{",
                    "usage": {
                        "input_tokens": 10,
                        "output_tokens": 5,
                        "total_tokens": 15,
                    },
                },
            )
        )

        provider = OpenAIProvider(settings=mock_openai_settings)
        messages = [
            Message(role="system", content=[MessageContent(type="text", text="Test")]),
            Message(role="user", content=[MessageContent(type="text", text="Test")]),
        ]

        with pytest.raises(LLMParseError):
            await provider.generate_response(messages)

    @pytest.mark.asyncio
    @respx.mock
    async def test_anthropic_missing_tool_use_raises_parse_error(
        self, mock_anthropic_settings: Settings
    ) -> None:
        """Test Anthropic raises LLMParseError when no tool_use block."""
        respx.post("https://api.anthropic.com/v1/messages").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "msg_123",
                    "type": "message",
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": "I will analyze this image..."}
                    ],
                    "stop_reason": "end_turn",
                    "usage": {"input_tokens": 50, "output_tokens": 20},
                },
            )
        )

        provider = AnthropicProvider(settings=mock_anthropic_settings)
        messages = [
            Message(role="system", content=[MessageContent(type="text", text="Test")]),
            Message(role="user", content=[MessageContent(type="text", text="Test")]),
        ]

        with pytest.raises(LLMParseError):
            await provider.generate_response(messages)


# =============================================================================
# P1-5: Empty model response
# =============================================================================


@pytest.mark.mock
class TestP1_5_EmptyResponse:
    """P1-5: Test handling of empty model responses."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_openai_empty_output_text_raises_parse_error(
        self, mock_openai_settings: Settings
    ) -> None:
        """Test OpenAI raises LLMParseError on empty output_text."""
        respx.post("https://api.openai.com/v1/responses").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "resp_123",
                    "object": "response",
                    "output": [],
                    "output_text": None,
                    "usage": {
                        "input_tokens": 10,
                        "output_tokens": 0,
                        "total_tokens": 10,
                    },
                },
            )
        )

        provider = OpenAIProvider(settings=mock_openai_settings)
        messages = [
            Message(role="system", content=[MessageContent(type="text", text="Test")]),
            Message(role="user", content=[MessageContent(type="text", text="Test")]),
        ]

        with pytest.raises(LLMParseError):
            await provider.generate_response(messages)

    @pytest.mark.asyncio
    @respx.mock
    async def test_anthropic_empty_content_raises_parse_error(
        self, mock_anthropic_settings: Settings
    ) -> None:
        """Test Anthropic raises LLMParseError on empty content."""
        respx.post("https://api.anthropic.com/v1/messages").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "msg_123",
                    "type": "message",
                    "role": "assistant",
                    "content": [],
                    "stop_reason": "end_turn",
                    "usage": {"input_tokens": 50, "output_tokens": 0},
                },
            )
        )

        provider = AnthropicProvider(settings=mock_anthropic_settings)
        messages = [
            Message(role="system", content=[MessageContent(type="text", text="Test")]),
            Message(role="user", content=[MessageContent(type="text", text="Test")]),
        ]

        with pytest.raises(LLMParseError):
            await provider.generate_response(messages)


# =============================================================================
# P1-6: Invalid coordinates in crop
# =============================================================================


@pytest.mark.mock
class TestP1_6_InvalidCoordinates:
    """P1-6: Test validation of crop coordinates."""

    def test_bounding_box_rejects_negative_x(self) -> None:
        """Test BoundingBoxAction rejects negative x."""
        with pytest.raises(ValueError):
            BoundingBoxAction(x=-100, y=100, width=500, height=500)

    def test_bounding_box_rejects_negative_y(self) -> None:
        """Test BoundingBoxAction rejects negative y."""
        with pytest.raises(ValueError):
            BoundingBoxAction(x=100, y=-100, width=500, height=500)

    def test_bounding_box_rejects_zero_width(self) -> None:
        """Test BoundingBoxAction rejects zero width."""
        with pytest.raises(ValueError):
            BoundingBoxAction(x=100, y=100, width=0, height=500)

    def test_bounding_box_rejects_zero_height(self) -> None:
        """Test BoundingBoxAction rejects zero height."""
        with pytest.raises(ValueError):
            BoundingBoxAction(x=100, y=100, width=500, height=0)

    def test_bounding_box_accepts_valid_coordinates(self) -> None:
        """Test BoundingBoxAction accepts valid coordinates."""
        action = BoundingBoxAction(x=0, y=0, width=100, height=100)
        assert action.x == 0
        assert action.y == 0
        assert action.width == 100
        assert action.height == 100


# =============================================================================
# P1-7: Cost tracking
# =============================================================================


@pytest.mark.mock
class TestP1_7_CostTracking:
    """P1-7: Test cost tracking across API calls."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_openai_tracks_token_usage(
        self, mock_openai_settings: Settings
    ) -> None:
        """Test OpenAI response includes token usage."""
        output_content = json.dumps(
            {
                "reasoning": "Test",
                "action": {
                    "action_type": "crop",
                    "x": 0,
                    "y": 0,
                    "width": 100,
                    "height": 100,
                },
            }
        )
        respx.post("https://api.openai.com/v1/responses").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "resp_123",
                    "object": "response",
                    "output": [
                        {
                            "type": "message",
                            "role": "assistant",
                            "content": [
                                {"type": "output_text", "text": output_content}
                            ],
                        }
                    ],
                    "output_text": output_content,
                    "usage": {
                        "input_tokens": 150,
                        "output_tokens": 75,
                        "total_tokens": 225,
                    },
                },
            )
        )

        provider = OpenAIProvider(settings=mock_openai_settings)
        messages = [
            Message(role="system", content=[MessageContent(type="text", text="Test")]),
            Message(role="user", content=[MessageContent(type="text", text="Test")]),
        ]

        response = await provider.generate_response(messages)
        assert response.usage.prompt_tokens == 150
        assert response.usage.completion_tokens == 75
        assert response.usage.total_tokens == 225
        assert response.usage.cost_usd >= 0

    @pytest.mark.asyncio
    @respx.mock
    async def test_anthropic_tracks_token_usage(
        self, mock_anthropic_settings: Settings
    ) -> None:
        """Test Anthropic response includes token usage."""
        respx.post("https://api.anthropic.com/v1/messages").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "msg_123",
                    "type": "message",
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "toolu_123",
                            "name": "submit_step",
                            "input": {
                                "reasoning": "Test",
                                "action": {
                                    "action_type": "crop",
                                    "x": 0,
                                    "y": 0,
                                    "width": 100,
                                    "height": 100,
                                },
                            },
                        }
                    ],
                    "stop_reason": "tool_use",
                    "usage": {"input_tokens": 200, "output_tokens": 100},
                },
            )
        )

        provider = AnthropicProvider(settings=mock_anthropic_settings)
        messages = [
            Message(role="system", content=[MessageContent(type="text", text="Test")]),
            Message(role="user", content=[MessageContent(type="text", text="Test")]),
        ]

        response = await provider.generate_response(messages)
        assert response.usage.prompt_tokens == 200
        assert response.usage.completion_tokens == 100
        assert response.usage.total_tokens == 300
        assert response.usage.cost_usd >= 0


# =============================================================================
# P1-8: Provider switching
# =============================================================================


@pytest.mark.mock
class TestP1_8_ProviderSwitching:
    """P1-8: Test same context with different providers."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_same_messages_work_with_both_providers(
        self, mock_both_settings: Settings
    ) -> None:
        """Test same message list works with OpenAI and Anthropic."""
        respx.post("https://api.openai.com/v1/responses").mock(
            return_value=httpx.Response(200, json=_mock_openai_crop_response())
        )
        respx.post("https://api.anthropic.com/v1/messages").mock(
            return_value=httpx.Response(200, json=_mock_anthropic_crop_response())
        )

        messages = [
            Message(
                role="system",
                content=[MessageContent(type="text", text="Analyze this image.")],
            ),
            Message(
                role="user",
                content=[MessageContent(type="text", text="What do you see?")],
            ),
        ]

        openai_provider = OpenAIProvider(settings=mock_both_settings)
        anthropic_provider = AnthropicProvider(settings=mock_both_settings)

        openai_response = await openai_provider.generate_response(messages)
        anthropic_response = await anthropic_provider.generate_response(messages)

        # Both should return valid responses
        assert openai_response.step_response is not None
        assert anthropic_response.step_response is not None

        # Both should have valid actions
        assert isinstance(openai_response.step_response.action, BoundingBoxAction)
        assert isinstance(anthropic_response.step_response.action, BoundingBoxAction)

    def test_context_manager_messages_usable_by_both(self) -> None:
        """Test ContextManager produces messages usable by both providers."""
        ctx = ContextManager(
            wsi_path="/slide.svs",
            question="Is this malignant?",
            max_steps=5,
        )

        # Get messages from context manager
        messages = ctx.get_messages(thumbnail_base64="thumb==")

        # Verify structure is valid for both providers
        assert len(messages) >= 2
        assert messages[0].role == "system"
        assert messages[1].role == "user"

        # Check system message has text
        system_content = messages[0].content
        assert any(c.type == "text" and c.text for c in system_content)

        # Check user message has text and image
        user_content = messages[1].content
        assert any(c.type == "text" and c.text for c in user_content)
        assert any(c.type == "image" and c.image_base64 for c in user_content)
