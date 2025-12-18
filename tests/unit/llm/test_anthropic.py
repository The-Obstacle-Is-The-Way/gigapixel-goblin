"""Tests for giant.llm.anthropic_client module."""

import base64
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from giant.config import Settings
from giant.llm.anthropic_client import (
    AnthropicProvider,
    _build_submit_step_tool,
    _parse_tool_use_to_step_response,
)
from giant.llm.protocol import (
    BoundingBoxAction,
    FinalAnswerAction,
    LLMError,
    LLMParseError,
    Message,
    MessageContent,
)


@pytest.fixture
def test_settings() -> Settings:
    """Create test settings with API key."""
    return Settings(
        OPENAI_API_KEY="test-key",
        ANTHROPIC_API_KEY="test-key",
        ANTHROPIC_RPM=1000,  # High limit for tests
        IMAGE_SIZE_ANTHROPIC=500,
        _env_file=None,  # type: ignore[call-arg]
    )


@pytest.fixture
def sample_messages() -> list[Message]:
    """Create sample messages for testing."""
    image = Image.new("RGB", (10, 10), color=(255, 0, 0))
    buf = BytesIO()
    image.save(buf, format="JPEG", quality=85)
    image_b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    return [
        Message(
            role="system",
            content=[MessageContent(type="text", text="You are a pathologist.")],
        ),
        Message(
            role="user",
            content=[
                MessageContent(type="text", text="What do you see?"),
                MessageContent(type="image", image_base64=image_b64),
            ],
        ),
    ]


class TestBuildSubmitStepTool:
    """Tests for tool definition builder."""

    def test_tool_has_correct_name(self) -> None:
        """Test that tool has correct name."""
        tool = _build_submit_step_tool()
        assert tool["name"] == "submit_step"

    def test_tool_has_required_properties(self) -> None:
        """Test that tool schema has required properties."""
        tool = _build_submit_step_tool()
        props = tool["input_schema"]["properties"]
        assert "reasoning" in props
        assert "action" in props

    def test_tool_requires_reasoning_and_action(self) -> None:
        """Test that reasoning and action are required."""
        tool = _build_submit_step_tool()
        required = tool["input_schema"]["required"]
        assert "reasoning" in required
        assert "action" in required


class TestParseToolUseToStepResponse:
    """Tests for tool use parsing."""

    def test_parse_crop_action(self) -> None:
        """Test parsing crop action from tool use."""
        tool_input = {
            "reasoning": "I see a suspicious region",
            "action": {
                "action_type": "crop",
                "x": 100,
                "y": 200,
                "width": 300,
                "height": 400,
            },
        }
        response = _parse_tool_use_to_step_response(tool_input)

        assert response.reasoning == "I see a suspicious region"
        assert isinstance(response.action, BoundingBoxAction)
        assert response.action.x == 100
        assert response.action.y == 200
        assert response.action.width == 300
        assert response.action.height == 400

    def test_parse_answer_action(self) -> None:
        """Test parsing answer action from tool use."""
        tool_input = {
            "reasoning": "Based on my analysis",
            "action": {
                "action_type": "answer",
                "answer_text": "This is benign tissue",
            },
        }
        response = _parse_tool_use_to_step_response(tool_input)

        assert response.reasoning == "Based on my analysis"
        assert isinstance(response.action, FinalAnswerAction)
        assert response.action.answer_text == "This is benign tissue"

    def test_parse_answer_without_text_raises(self) -> None:
        """Test that answer without text raises error."""
        tool_input = {
            "reasoning": "Analysis",
            "action": {"action_type": "answer", "answer_text": ""},
        }
        with pytest.raises(LLMParseError) as exc_info:
            _parse_tool_use_to_step_response(tool_input)
        assert "answer_text" in str(exc_info.value)

    def test_parse_unknown_action_type_raises(self) -> None:
        """Test that unknown action type raises error."""
        tool_input = {
            "reasoning": "Test",
            "action": {"action_type": "unknown"},
        }
        with pytest.raises(LLMParseError) as exc_info:
            _parse_tool_use_to_step_response(tool_input)
        assert "unknown" in str(exc_info.value).lower()

    def test_parse_crop_missing_fields_raises(self) -> None:
        """Test that crop action missing required fields raises error."""
        tool_input = {
            "reasoning": "Test",
            "action": {"action_type": "crop", "x": 0},
        }
        with pytest.raises(LLMParseError):
            _parse_tool_use_to_step_response(tool_input)


class TestAnthropicProviderInit:
    """Tests for AnthropicProvider initialization."""

    def test_init_with_default_model(self, test_settings: Settings) -> None:
        """Test initialization with default model."""
        provider = AnthropicProvider(settings=test_settings)
        assert provider.model == "claude-opus-4-5-20251101"
        assert provider.get_model_name() == "claude-opus-4-5-20251101"

    def test_init_with_custom_model(self, test_settings: Settings) -> None:
        """Test initialization with custom model."""
        provider = AnthropicProvider(
            model="claude-3-opus-20240229", settings=test_settings
        )
        assert provider.model == "claude-3-opus-20240229"

    def test_get_target_size(self, test_settings: Settings) -> None:
        """Test target size from settings."""
        provider = AnthropicProvider(settings=test_settings)
        assert provider.get_target_size() == 500


class TestAnthropicProviderGenerate:
    """Tests for AnthropicProvider.generate_response."""

    @pytest.mark.asyncio
    async def test_successful_crop_response(
        self, test_settings: Settings, sample_messages: list[Message]
    ) -> None:
        """Test successful response with crop action."""
        provider = AnthropicProvider(settings=test_settings)

        # Mock response with tool use
        mock_tool_block = MagicMock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.name = "submit_step"
        mock_tool_block.input = {
            "reasoning": "I see a suspicious region",
            "action": {
                "action_type": "crop",
                "x": 100,
                "y": 200,
                "width": 300,
                "height": 400,
            },
        }

        mock_response = MagicMock()
        mock_response.content = [mock_tool_block]
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)

        with patch.object(
            provider._client.messages, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_response

            result = await provider.generate_response(sample_messages)

            assert result.step_response.reasoning == "I see a suspicious region"
            assert result.step_response.action.action_type == "crop"
            assert result.usage.prompt_tokens == 100
            assert result.usage.completion_tokens == 50
            assert result.model == "claude-opus-4-5-20251101"
            assert result.latency_ms > 0

    @pytest.mark.asyncio
    async def test_successful_answer_response(
        self, test_settings: Settings, sample_messages: list[Message]
    ) -> None:
        """Test successful response with answer action."""
        provider = AnthropicProvider(settings=test_settings)

        mock_tool_block = MagicMock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.name = "submit_step"
        mock_tool_block.input = {
            "reasoning": "Based on analysis",
            "action": {"action_type": "answer", "answer_text": "Benign tissue"},
        }

        mock_response = MagicMock()
        mock_response.content = [mock_tool_block]
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)

        with patch.object(
            provider._client.messages, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_response

            result = await provider.generate_response(sample_messages)

            assert result.step_response.action.action_type == "answer"
            assert result.step_response.action.answer_text == "Benign tissue"

    @pytest.mark.asyncio
    async def test_parse_error_on_missing_tool_use(
        self, test_settings: Settings, sample_messages: list[Message]
    ) -> None:
        """Test that missing tool use raises LLMParseError."""
        provider = AnthropicProvider(settings=test_settings)

        # Response with text only, no tool use
        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_text_block.text = "I cannot help with that."

        mock_response = MagicMock()
        mock_response.content = [mock_text_block]
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)

        with patch.object(
            provider._client.messages, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_response

            with pytest.raises(LLMParseError) as exc_info:
                await provider.generate_response(sample_messages)

            assert "No submit_step tool use" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_api_called_with_tool_choice(
        self, test_settings: Settings, sample_messages: list[Message]
    ) -> None:
        """Test that API is called with forced tool choice."""
        provider = AnthropicProvider(settings=test_settings)

        mock_tool_block = MagicMock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.name = "submit_step"
        mock_tool_block.input = {
            "reasoning": "Test",
            "action": {
                "action_type": "crop",
                "x": 0,
                "y": 0,
                "width": 100,
                "height": 100,
            },
        }

        mock_response = MagicMock()
        mock_response.content = [mock_tool_block]
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)

        with patch.object(
            provider._client.messages, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_response

            await provider.generate_response(sample_messages)

            # Verify tool_choice was passed
            call_kwargs = mock_create.call_args.kwargs
            assert call_kwargs["tool_choice"] == {
                "type": "tool",
                "name": "submit_step",
            }


class TestAnthropicProviderCircuitBreaker:
    """Tests for circuit breaker integration."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_on_failures(
        self, test_settings: Settings, sample_messages: list[Message]
    ) -> None:
        """Test that circuit breaker opens after failures."""
        provider = AnthropicProvider(settings=test_settings)
        provider._circuit_breaker.config.failure_threshold = 2

        with patch.object(
            provider._client.messages, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.side_effect = Exception("API Error")

            # First failure
            with pytest.raises(LLMError):
                await provider.generate_response(sample_messages)

            # Second failure - should open circuit
            with pytest.raises(LLMError):
                await provider.generate_response(sample_messages)

            assert provider._circuit_breaker.is_open
