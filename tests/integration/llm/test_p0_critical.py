"""P0: Critical Path Integration Tests.

These tests validate the agent loop can function.
MUST PASS before proceeding to Spec-09.

Tests can run in two modes:
1. Mock mode (default): Uses respx to mock HTTP calls for CI/CD
2. Live mode: Requires API keys, makes real API calls

Run mock tests:
    uv run pytest tests/integration/llm/test_p0_critical.py -v -m mock

Run live tests:
    OPENAI_API_KEY=sk-... ANTHROPIC_API_KEY=sk-ant-... \
    uv run pytest tests/integration/llm/test_p0_critical.py -v -m live
"""

from __future__ import annotations

import base64
import json
import os
from typing import Any

import httpx
import pytest
import respx

from giant.agent.context import ContextManager
from giant.config import Settings
from giant.llm import (
    AnthropicProvider,
    BoundingBoxAction,
    FinalAnswerAction,
    Message,
    MessageContent,
    OpenAIProvider,
    StepResponse,
    create_provider,
)
from giant.prompts.builder import PromptBuilder

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


def _has_openai_key() -> bool:
    """Check if real OpenAI API key is available (shell env OR .env file)."""
    # Check shell env first, then fall back to settings (which reads .env)
    if os.getenv("OPENAI_API_KEY"):
        return True
    from giant.config import Settings

    s = Settings()
    return s.OPENAI_API_KEY is not None and s.OPENAI_API_KEY.strip() != ""


def _has_anthropic_key() -> bool:
    """Check if real Anthropic API key is available (shell env OR .env file)."""
    # Check shell env first, then fall back to settings (which reads .env)
    if os.getenv("ANTHROPIC_API_KEY"):
        return True
    from giant.config import Settings

    s = Settings()
    return s.ANTHROPIC_API_KEY is not None and s.ANTHROPIC_API_KEY.strip() != ""


@pytest.fixture
def has_openai_key() -> bool:
    """Check if real OpenAI API key is available."""
    return _has_openai_key()


@pytest.fixture
def has_anthropic_key() -> bool:
    """Check if real Anthropic API key is available."""
    return _has_anthropic_key()


@pytest.fixture
def sample_text_message() -> list[Message]:
    """Create a minimal text-only message list."""
    return [
        Message(
            role="system",
            content=[MessageContent(type="text", text="You are a helpful assistant.")],
        ),
        Message(
            role="user",
            content=[MessageContent(type="text", text="Say hello.")],
        ),
    ]


@pytest.fixture
def sample_image_base64() -> str:
    """Create a minimal valid base64 image (1x1 red JPEG)."""
    # Minimal 1x1 red JPEG
    jpeg_bytes = bytes(
        [
            0xFF,
            0xD8,
            0xFF,
            0xE0,
            0x00,
            0x10,
            0x4A,
            0x46,
            0x49,
            0x46,
            0x00,
            0x01,
            0x01,
            0x00,
            0x00,
            0x01,
            0x00,
            0x01,
            0x00,
            0x00,
            0xFF,
            0xDB,
            0x00,
            0x43,
            0x00,
            0x08,
            0x06,
            0x06,
            0x07,
            0x06,
            0x05,
            0x08,
            0x07,
            0x07,
            0x07,
            0x09,
            0x09,
            0x08,
            0x0A,
            0x0C,
            0x14,
            0x0D,
            0x0C,
            0x0B,
            0x0B,
            0x0C,
            0x19,
            0x12,
            0x13,
            0x0F,
            0x14,
            0x1D,
            0x1A,
            0x1F,
            0x1E,
            0x1D,
            0x1A,
            0x1C,
            0x1C,
            0x20,
            0x24,
            0x2E,
            0x27,
            0x20,
            0x22,
            0x2C,
            0x23,
            0x1C,
            0x1C,
            0x28,
            0x37,
            0x29,
            0x2C,
            0x30,
            0x31,
            0x34,
            0x34,
            0x34,
            0x1F,
            0x27,
            0x39,
            0x3D,
            0x38,
            0x32,
            0x3C,
            0x2E,
            0x33,
            0x34,
            0x32,
            0xFF,
            0xC0,
            0x00,
            0x0B,
            0x08,
            0x00,
            0x01,
            0x00,
            0x01,
            0x01,
            0x01,
            0x11,
            0x00,
            0xFF,
            0xC4,
            0x00,
            0x1F,
            0x00,
            0x00,
            0x01,
            0x05,
            0x01,
            0x01,
            0x01,
            0x01,
            0x01,
            0x01,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x01,
            0x02,
            0x03,
            0x04,
            0x05,
            0x06,
            0x07,
            0x08,
            0x09,
            0x0A,
            0x0B,
            0xFF,
            0xC4,
            0x00,
            0xB5,
            0x10,
            0x00,
            0x02,
            0x01,
            0x03,
            0x03,
            0x02,
            0x04,
            0x03,
            0x05,
            0x05,
            0x04,
            0x04,
            0x00,
            0x00,
            0x01,
            0x7D,
            0x01,
            0x02,
            0x03,
            0x00,
            0x04,
            0x11,
            0x05,
            0x12,
            0x21,
            0x31,
            0x41,
            0x06,
            0x13,
            0x51,
            0x61,
            0x07,
            0x22,
            0x71,
            0x14,
            0x32,
            0x81,
            0x91,
            0xA1,
            0x08,
            0x23,
            0x42,
            0xB1,
            0xC1,
            0x15,
            0x52,
            0xD1,
            0xF0,
            0x24,
            0x33,
            0x62,
            0x72,
            0x82,
            0x09,
            0x0A,
            0x16,
            0x17,
            0x18,
            0x19,
            0x1A,
            0x25,
            0x26,
            0x27,
            0x28,
            0x29,
            0x2A,
            0x34,
            0x35,
            0x36,
            0x37,
            0x38,
            0x39,
            0x3A,
            0x43,
            0x44,
            0x45,
            0x46,
            0x47,
            0x48,
            0x49,
            0x4A,
            0x53,
            0x54,
            0x55,
            0x56,
            0x57,
            0x58,
            0x59,
            0x5A,
            0x63,
            0x64,
            0x65,
            0x66,
            0x67,
            0x68,
            0x69,
            0x6A,
            0x73,
            0x74,
            0x75,
            0x76,
            0x77,
            0x78,
            0x79,
            0x7A,
            0x83,
            0x84,
            0x85,
            0x86,
            0x87,
            0x88,
            0x89,
            0x8A,
            0x92,
            0x93,
            0x94,
            0x95,
            0x96,
            0x97,
            0x98,
            0x99,
            0x9A,
            0xA2,
            0xA3,
            0xA4,
            0xA5,
            0xA6,
            0xA7,
            0xA8,
            0xA9,
            0xAA,
            0xB2,
            0xB3,
            0xB4,
            0xB5,
            0xB6,
            0xB7,
            0xB8,
            0xB9,
            0xBA,
            0xC2,
            0xC3,
            0xC4,
            0xC5,
            0xC6,
            0xC7,
            0xC8,
            0xC9,
            0xCA,
            0xD2,
            0xD3,
            0xD4,
            0xD5,
            0xD6,
            0xD7,
            0xD8,
            0xD9,
            0xDA,
            0xE1,
            0xE2,
            0xE3,
            0xE4,
            0xE5,
            0xE6,
            0xE7,
            0xE8,
            0xE9,
            0xEA,
            0xF1,
            0xF2,
            0xF3,
            0xF4,
            0xF5,
            0xF6,
            0xF7,
            0xF8,
            0xF9,
            0xFA,
            0xFF,
            0xDA,
            0x00,
            0x08,
            0x01,
            0x01,
            0x00,
            0x00,
            0x3F,
            0x00,
            0xFB,
            0xD5,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0xFF,
            0xD9,
        ]
    )
    return base64.b64encode(jpeg_bytes).decode("ascii")


@pytest.fixture
def sample_image_message(sample_image_base64: str) -> list[Message]:
    """Create a message list with an image."""
    return [
        Message(
            role="system",
            content=[
                MessageContent(
                    type="text",
                    text="You are GIANT, an AI that analyzes pathology images.",
                )
            ],
        ),
        Message(
            role="user",
            content=[
                MessageContent(
                    type="text",
                    text="What do you see in this image?",
                ),
                MessageContent(
                    type="image",
                    image_base64=sample_image_base64,
                    media_type="image/jpeg",
                ),
            ],
        ),
    ]


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
                                "reasoning": "I see a suspicious region at coordinates (100, 200). I will crop to examine it more closely.",
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
                "reasoning": "I see a suspicious region at coordinates (100, 200). I will crop to examine it more closely.",
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


def _mock_openai_answer_response() -> dict[str, Any]:
    """Create a mock OpenAI response with answer action."""
    return {
        "id": "resp_456",
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
                                "reasoning": "Based on my analysis, this tissue shows normal morphology.",
                                "action": {
                                    "action_type": "answer",
                                    "answer_text": "The tissue appears normal with no malignant features.",
                                },
                            }
                        ),
                    }
                ],
            }
        ],
        "output_text": json.dumps(
            {
                "reasoning": "Based on my analysis, this tissue shows normal morphology.",
                "action": {
                    "action_type": "answer",
                    "answer_text": "The tissue appears normal with no malignant features.",
                },
            }
        ),
        "usage": {
            "input_tokens": 150,
            "output_tokens": 40,
            "total_tokens": 190,
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
                    "reasoning": "I observe an area of interest. Let me zoom in to examine.",
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


def _mock_anthropic_answer_response() -> dict[str, Any]:
    """Create a mock Anthropic response with answer action."""
    return {
        "id": "msg_456",
        "type": "message",
        "role": "assistant",
        "content": [
            {
                "type": "tool_use",
                "id": "toolu_456",
                "name": "submit_step",
                "input": {
                    "reasoning": "After examining the tissue, I can provide a diagnosis.",
                    "action": {
                        "action_type": "answer",
                        "answer_text": "This is benign tissue with no abnormalities.",
                    },
                },
            }
        ],
        "model": "claude-opus-4-5-20251101",
        "stop_reason": "tool_use",
        "usage": {
            "input_tokens": 180,
            "output_tokens": 45,
        },
    }


# =============================================================================
# P0-1: OpenAI provider init
# =============================================================================


@pytest.mark.mock
class TestP0_1_OpenAIProviderInit:
    """P0-1: Test OpenAI provider initialization."""

    def test_openai_provider_init_success(self, mock_openai_settings: Settings) -> None:
        """Test that OpenAI provider initializes without error."""
        provider = OpenAIProvider(
            model="gpt-5.2-2025-12-11",
            settings=mock_openai_settings,
        )
        assert provider.get_model_name() == "gpt-5.2-2025-12-11"
        assert provider.get_target_size() == 1000

    def test_openai_provider_via_factory_requires_real_env(self) -> None:
        """Test factory function depends on env - just test it doesn't crash on model check."""
        # Factory uses global settings, so just verify model validation
        with pytest.raises(ValueError, match="not approved"):
            create_provider("openai", model="gpt-4o")

    def test_openai_provider_rejects_invalid_model(
        self, mock_openai_settings: Settings
    ) -> None:
        """Test that invalid models are rejected."""
        with pytest.raises(ValueError, match="not approved"):
            OpenAIProvider(model="gpt-4o", settings=mock_openai_settings)


# =============================================================================
# P0-2: Anthropic provider init
# =============================================================================


@pytest.mark.mock
class TestP0_2_AnthropicProviderInit:
    """P0-2: Test Anthropic provider initialization."""

    def test_anthropic_provider_init_success(
        self, mock_anthropic_settings: Settings
    ) -> None:
        """Test that Anthropic provider initializes without error."""
        provider = AnthropicProvider(
            model="claude-opus-4-5-20251101",
            settings=mock_anthropic_settings,
        )
        assert provider.get_model_name() == "claude-opus-4-5-20251101"
        assert provider.get_target_size() == 500

    def test_anthropic_provider_via_factory_requires_real_env(self) -> None:
        """Test factory function depends on env - just test it doesn't crash on model check."""
        # Factory uses global settings, so just verify model validation
        with pytest.raises(ValueError, match="not approved"):
            create_provider("anthropic", model="claude-3-opus-20240229")

    def test_anthropic_provider_rejects_invalid_model(
        self, mock_anthropic_settings: Settings
    ) -> None:
        """Test that invalid models are rejected."""
        with pytest.raises(ValueError, match="not approved"):
            AnthropicProvider(
                model="claude-3-opus-20240229",
                settings=mock_anthropic_settings,
            )


# =============================================================================
# P0-3: Send text message
# =============================================================================


@pytest.mark.mock
class TestP0_3_SendTextMessage:
    """P0-3: Test sending text-only messages."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_openai_send_text_message(
        self,
        mock_openai_settings: Settings,
        sample_text_message: list[Message],
    ) -> None:
        """Test sending text message to OpenAI."""
        respx.post("https://api.openai.com/v1/responses").mock(
            return_value=httpx.Response(200, json=_mock_openai_answer_response())
        )

        provider = OpenAIProvider(settings=mock_openai_settings)
        response = await provider.generate_response(sample_text_message)

        assert response.step_response is not None
        assert response.step_response.reasoning != ""
        assert response.usage.total_tokens > 0

    @pytest.mark.asyncio
    @respx.mock
    async def test_anthropic_send_text_message(
        self,
        mock_anthropic_settings: Settings,
        sample_text_message: list[Message],
    ) -> None:
        """Test sending text message to Anthropic."""
        respx.post("https://api.anthropic.com/v1/messages").mock(
            return_value=httpx.Response(200, json=_mock_anthropic_answer_response())
        )

        provider = AnthropicProvider(settings=mock_anthropic_settings)
        response = await provider.generate_response(sample_text_message)

        assert response.step_response is not None
        assert response.step_response.reasoning != ""
        assert response.usage.total_tokens > 0


# =============================================================================
# P0-4: Send image message
# =============================================================================


@pytest.mark.mock
class TestP0_4_SendImageMessage:
    """P0-4: Test sending messages with images."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_openai_send_image_message(
        self,
        mock_openai_settings: Settings,
        sample_image_message: list[Message],
    ) -> None:
        """Test sending image message to OpenAI."""
        respx.post("https://api.openai.com/v1/responses").mock(
            return_value=httpx.Response(200, json=_mock_openai_crop_response())
        )

        provider = OpenAIProvider(settings=mock_openai_settings)
        response = await provider.generate_response(sample_image_message)

        assert response.step_response is not None
        assert isinstance(response.step_response.action, BoundingBoxAction)

    @pytest.mark.asyncio
    @respx.mock
    async def test_anthropic_send_image_message(
        self,
        mock_anthropic_settings: Settings,
        sample_image_message: list[Message],
    ) -> None:
        """Test sending image message to Anthropic."""
        respx.post("https://api.anthropic.com/v1/messages").mock(
            return_value=httpx.Response(200, json=_mock_anthropic_crop_response())
        )

        provider = AnthropicProvider(settings=mock_anthropic_settings)
        response = await provider.generate_response(sample_image_message)

        assert response.step_response is not None
        assert isinstance(response.step_response.action, BoundingBoxAction)


# =============================================================================
# P0-5: System prompt applied
# =============================================================================


@pytest.mark.mock
class TestP0_5_SystemPromptApplied:
    """P0-5: Test that system prompt is properly applied."""

    def test_system_prompt_in_first_position(self) -> None:
        """Test that PromptBuilder puts system message first."""
        builder = PromptBuilder()
        system_msg = builder.build_system_message()

        assert system_msg.role == "system"
        assert len(system_msg.content) == 1
        assert system_msg.content[0].type == "text"
        assert "GIANT" in (system_msg.content[0].text or "")

    def test_context_manager_messages_start_with_system(self) -> None:
        """Test ContextManager puts system message first."""
        ctx = ContextManager(
            wsi_path="/slide.svs",
            question="Is this malignant?",
            max_steps=5,
        )
        messages = ctx.get_messages(thumbnail_base64="thumb==")

        assert len(messages) >= 2
        assert messages[0].role == "system"
        assert messages[1].role == "user"


# =============================================================================
# P0-6: User prompt construction
# =============================================================================


@pytest.mark.mock
class TestP0_6_UserPromptConstruction:
    """P0-6: Test user prompt contains required elements."""

    def test_user_message_contains_question(self) -> None:
        """Test user message includes the question."""
        builder = PromptBuilder()
        user_msg = builder.build_user_message(
            question="Is this tissue malignant?",
            step=1,
            max_steps=5,
            context_images=["thumb=="],
        )

        assert user_msg.role == "user"
        text_content = next(c for c in user_msg.content if c.type == "text")
        assert "Is this tissue malignant?" in (text_content.text or "")

    def test_user_message_contains_step_count(self) -> None:
        """Test user message includes step information."""
        builder = PromptBuilder()
        user_msg = builder.build_user_message(
            question="Q?",
            step=2,
            max_steps=5,
            context_images=["img=="],
            last_region="(100, 200, 300, 400)",
        )

        text_content = next(c for c in user_msg.content if c.type == "text")
        text = text_content.text or ""
        assert "2" in text  # Step 2
        assert "5" in text  # max_steps 5

    def test_user_message_includes_images(self) -> None:
        """Test user message includes image content."""
        builder = PromptBuilder()
        user_msg = builder.build_user_message(
            question="Q?",
            step=1,
            max_steps=5,
            context_images=["imagedata=="],
        )

        image_contents = [c for c in user_msg.content if c.type == "image"]
        assert len(image_contents) == 1
        assert image_contents[0].image_base64 == "imagedata=="


# =============================================================================
# P0-7: Context accumulation
# =============================================================================


@pytest.mark.mock
class TestP0_7_ContextAccumulation:
    """P0-7: Test context accumulation over multiple turns."""

    def test_three_turns_alternating_messages(self) -> None:
        """Test that 3 turns produce alternating user/assistant."""
        ctx = ContextManager(
            wsi_path="/slide.svs",
            question="Is this malignant?",
            max_steps=10,
        )

        # Add 3 turns
        for i in range(3):
            response = StepResponse(
                reasoning=f"Step {i} reasoning",
                action=BoundingBoxAction(x=i * 100, y=i * 100, width=200, height=200),
            )
            ctx.add_turn(image_base64=f"img{i}==", response=response)

        messages = ctx.get_messages(thumbnail_base64="thumb==")

        # Structure: system, user0, assistant0, user1, assistant1, user2, assistant2
        assert len(messages) == 7
        roles = [m.role for m in messages]
        assert roles == [
            "system",
            "user",
            "assistant",
            "user",
            "assistant",
            "user",
            "assistant",
        ]

    def test_trajectory_tracks_all_turns(self) -> None:
        """Test that trajectory correctly tracks all turns."""
        ctx = ContextManager(
            wsi_path="/slide.svs",
            question="Q?",
            max_steps=5,
        )

        # Add turns
        for i in range(3):
            response = StepResponse(
                reasoning=f"R{i}",
                action=BoundingBoxAction(x=0, y=0, width=100, height=100),
            )
            ctx.add_turn(image_base64=f"img{i}==", response=response)

        assert len(ctx.trajectory.turns) == 3
        assert ctx.trajectory.turns[0].step_index == 0
        assert ctx.trajectory.turns[1].step_index == 1
        assert ctx.trajectory.turns[2].step_index == 2


# =============================================================================
# P0-8: Parse crop action
# =============================================================================


@pytest.mark.mock
class TestP0_8_ParseCropAction:
    """P0-8: Test parsing of crop action from model response."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_openai_parses_crop_action(
        self, mock_openai_settings: Settings
    ) -> None:
        """Test OpenAI response parses to BoundingBoxAction."""
        respx.post("https://api.openai.com/v1/responses").mock(
            return_value=httpx.Response(200, json=_mock_openai_crop_response())
        )

        provider = OpenAIProvider(settings=mock_openai_settings)
        messages = [
            Message(role="system", content=[MessageContent(type="text", text="Test")]),
            Message(role="user", content=[MessageContent(type="text", text="Test")]),
        ]
        response = await provider.generate_response(messages)

        action = response.step_response.action
        assert isinstance(action, BoundingBoxAction)
        assert action.action_type == "crop"
        assert action.x == 100
        assert action.y == 200
        assert action.width == 500
        assert action.height == 500

    @pytest.mark.asyncio
    @respx.mock
    async def test_anthropic_parses_crop_action(
        self, mock_anthropic_settings: Settings
    ) -> None:
        """Test Anthropic response parses to BoundingBoxAction."""
        respx.post("https://api.anthropic.com/v1/messages").mock(
            return_value=httpx.Response(200, json=_mock_anthropic_crop_response())
        )

        provider = AnthropicProvider(settings=mock_anthropic_settings)
        messages = [
            Message(role="system", content=[MessageContent(type="text", text="Test")]),
            Message(role="user", content=[MessageContent(type="text", text="Test")]),
        ]
        response = await provider.generate_response(messages)

        action = response.step_response.action
        assert isinstance(action, BoundingBoxAction)
        assert action.action_type == "crop"
        assert action.x == 150
        assert action.y == 250


# =============================================================================
# P0-9: Parse answer action
# =============================================================================


@pytest.mark.mock
class TestP0_9_ParseAnswerAction:
    """P0-9: Test parsing of answer action from model response."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_openai_parses_answer_action(
        self, mock_openai_settings: Settings
    ) -> None:
        """Test OpenAI response parses to FinalAnswerAction."""
        respx.post("https://api.openai.com/v1/responses").mock(
            return_value=httpx.Response(200, json=_mock_openai_answer_response())
        )

        provider = OpenAIProvider(settings=mock_openai_settings)
        messages = [
            Message(role="system", content=[MessageContent(type="text", text="Test")]),
            Message(role="user", content=[MessageContent(type="text", text="Test")]),
        ]
        response = await provider.generate_response(messages)

        action = response.step_response.action
        assert isinstance(action, FinalAnswerAction)
        assert action.action_type == "answer"
        assert "normal" in action.answer_text.lower()

    @pytest.mark.asyncio
    @respx.mock
    async def test_anthropic_parses_answer_action(
        self, mock_anthropic_settings: Settings
    ) -> None:
        """Test Anthropic response parses to FinalAnswerAction."""
        respx.post("https://api.anthropic.com/v1/messages").mock(
            return_value=httpx.Response(200, json=_mock_anthropic_answer_response())
        )

        provider = AnthropicProvider(settings=mock_anthropic_settings)
        messages = [
            Message(role="system", content=[MessageContent(type="text", text="Test")]),
            Message(role="user", content=[MessageContent(type="text", text="Test")]),
        ]
        response = await provider.generate_response(messages)

        action = response.step_response.action
        assert isinstance(action, FinalAnswerAction)
        assert action.action_type == "answer"
        assert "benign" in action.answer_text.lower()

    def test_context_manager_sets_final_answer(self) -> None:
        """Test ContextManager captures final answer in trajectory."""
        ctx = ContextManager(
            wsi_path="/slide.svs",
            question="Q?",
            max_steps=5,
        )

        response = StepResponse(
            reasoning="Analysis complete",
            action=FinalAnswerAction(answer_text="Malignant adenocarcinoma"),
        )
        ctx.add_turn(image_base64="img==", response=response)

        assert ctx.trajectory.final_answer == "Malignant adenocarcinoma"


# =============================================================================
# Live API Tests (require real API keys)
# =============================================================================


@pytest.mark.live
@pytest.mark.cost
@pytest.mark.skipif(
    not _has_openai_key(),
    reason="OPENAI_API_KEY not set (shell env or .env file)",
)
class TestLiveOpenAI:
    """Live tests with real OpenAI API (requires OPENAI_API_KEY).

    These tests make real API calls and incur costs.
    Run with: pytest -m live
    """

    @pytest.mark.asyncio
    async def test_live_openai_text_message(self) -> None:
        """Test real API call to OpenAI with text."""
        provider = OpenAIProvider()
        messages = [
            Message(
                role="system",
                content=[
                    MessageContent(
                        type="text",
                        text="You are a helpful assistant. Respond with a crop action in the required format.",
                    )
                ],
            ),
            Message(
                role="user",
                content=[
                    MessageContent(
                        type="text",
                        text="Analyze this pathology slide and crop a region of interest. Use crop(100, 100, 200, 200).",
                    )
                ],
            ),
        ]
        response = await provider.generate_response(messages)

        assert response.step_response is not None
        assert response.usage.total_tokens > 0
        assert response.latency_ms > 0


@pytest.mark.live
@pytest.mark.cost
@pytest.mark.skipif(
    not _has_anthropic_key(),
    reason="ANTHROPIC_API_KEY not set (shell env or .env file)",
)
class TestLiveAnthropic:
    """Live tests with real Anthropic API (requires ANTHROPIC_API_KEY).

    These tests make real API calls and incur costs.
    Run with: pytest -m live
    """

    @pytest.mark.asyncio
    async def test_live_anthropic_text_message(self) -> None:
        """Test real API call to Anthropic with text."""
        provider = AnthropicProvider()
        messages = [
            Message(
                role="system",
                content=[
                    MessageContent(
                        type="text",
                        text="You are a pathology assistant. Use the submit_step tool to respond.",
                    )
                ],
            ),
            Message(
                role="user",
                content=[
                    MessageContent(
                        type="text",
                        text="Analyze this region and provide your assessment.",
                    )
                ],
            ),
        ]
        response = await provider.generate_response(messages)

        assert response.step_response is not None
        assert response.usage.total_tokens > 0
        assert response.latency_ms > 0
