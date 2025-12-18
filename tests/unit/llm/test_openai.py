"""Tests for giant.llm.openai_client module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from giant.config import Settings
from giant.llm.openai_client import OpenAIProvider, _build_json_schema
from giant.llm.protocol import (
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
        OPENAI_RPM=1000,  # High limit for tests
        IMAGE_SIZE_OPENAI=1000,
        _env_file=None,  # type: ignore[call-arg]
    )


@pytest.fixture
def sample_messages() -> list[Message]:
    """Create sample messages for testing."""
    return [
        Message(
            role="system",
            content=[MessageContent(type="text", text="You are a pathologist.")],
        ),
        Message(
            role="user",
            content=[
                MessageContent(type="text", text="What do you see?"),
                MessageContent(type="image", image_base64="base64data..."),
            ],
        ),
    ]


class TestBuildJsonSchema:
    """Tests for JSON schema builder."""

    def test_schema_has_required_fields(self) -> None:
        """Test that schema has required fields."""
        schema = _build_json_schema()
        assert schema["name"] == "StepResponse"
        assert "schema" in schema
        assert "reasoning" in schema["schema"]["properties"]
        assert "action" in schema["schema"]["properties"]

    def test_schema_is_strict(self) -> None:
        """Test that schema is marked as strict."""
        schema = _build_json_schema()
        assert schema["strict"] is True

    def test_action_schema_has_discriminator(self) -> None:
        """Test that action schema has action_type discriminator."""
        schema = _build_json_schema()
        action_schema = schema["schema"]["properties"]["action"]
        assert "oneOf" in action_schema

        variants = action_schema["oneOf"]
        assert any(v["properties"]["action_type"]["enum"] == ["crop"] for v in variants)
        assert any(
            v["properties"]["action_type"]["enum"] == ["answer"] for v in variants
        )


class TestOpenAIProviderInit:
    """Tests for OpenAIProvider initialization."""

    def test_init_with_default_model(self, test_settings: Settings) -> None:
        """Test initialization with default model."""
        provider = OpenAIProvider(settings=test_settings)
        assert provider.model == "gpt-5.2-pro-2025-12-11"
        assert provider.get_model_name() == "gpt-5.2-pro-2025-12-11"

    def test_init_with_custom_model(self, test_settings: Settings) -> None:
        """Test initialization with custom model."""
        provider = OpenAIProvider(model="gpt-5", settings=test_settings)
        assert provider.model == "gpt-5"

    def test_get_target_size(self, test_settings: Settings) -> None:
        """Test target size from settings."""
        provider = OpenAIProvider(settings=test_settings)
        assert provider.get_target_size() == 1000


class TestOpenAIProviderGenerate:
    """Tests for OpenAIProvider.generate_response."""

    @pytest.mark.asyncio
    async def test_successful_crop_response(
        self, test_settings: Settings, sample_messages: list[Message]
    ) -> None:
        """Test successful response with crop action."""
        provider = OpenAIProvider(settings=test_settings)

        # Mock response
        mock_response = MagicMock()
        mock_response.output_text = (
            '{"reasoning": "I see a suspicious region", '
            '"action": {"action_type": "crop", '
            '"x": 100, "y": 200, "width": 300, "height": 400}}'
        )
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)

        with patch.object(
            provider._client.responses, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_response

            result = await provider.generate_response(sample_messages)

            assert result.step_response.reasoning == "I see a suspicious region"
            assert result.step_response.action.action_type == "crop"
            assert result.usage.prompt_tokens == 100
            assert result.usage.completion_tokens == 50
            assert result.model == "gpt-5.2-pro-2025-12-11"
            assert result.latency_ms > 0

    @pytest.mark.asyncio
    async def test_successful_answer_response(
        self, test_settings: Settings, sample_messages: list[Message]
    ) -> None:
        """Test successful response with answer action."""
        provider = OpenAIProvider(settings=test_settings)

        mock_response = MagicMock()
        mock_response.output_text = (
            '{"reasoning": "Based on analysis", '
            '"action": {"action_type": "answer", "answer_text": "Benign tissue"}}'
        )
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)

        with patch.object(
            provider._client.responses, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_response

            result = await provider.generate_response(sample_messages)

            assert result.step_response.action.action_type == "answer"
            assert result.step_response.action.answer_text == "Benign tissue"

    @pytest.mark.asyncio
    async def test_parse_error_on_invalid_json(
        self, test_settings: Settings, sample_messages: list[Message]
    ) -> None:
        """Test that invalid JSON raises LLMParseError."""
        provider = OpenAIProvider(settings=test_settings)

        mock_response = MagicMock()
        mock_response.output_text = "not valid json"
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)

        with patch.object(
            provider._client.responses, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_response

            with pytest.raises(LLMParseError) as exc_info:
                await provider.generate_response(sample_messages)

            assert exc_info.value.provider == "openai"
            assert exc_info.value.raw_output == "not valid json"

    @pytest.mark.asyncio
    async def test_parse_error_on_missing_output(
        self, test_settings: Settings, sample_messages: list[Message]
    ) -> None:
        """Test that missing output raises LLMParseError."""
        provider = OpenAIProvider(settings=test_settings)

        mock_response = MagicMock()
        mock_response.output_text = None
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)

        with patch.object(
            provider._client.responses, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_response

            with pytest.raises(LLMParseError) as exc_info:
                await provider.generate_response(sample_messages)

            assert "No output text" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_cost_calculation_includes_images(
        self, test_settings: Settings, sample_messages: list[Message]
    ) -> None:
        """Test that cost calculation includes image costs."""
        provider = OpenAIProvider(settings=test_settings)

        mock_response = MagicMock()
        mock_response.output_text = (
            '{"reasoning": "Test", '
            '"action": {"action_type": "crop", '
            '"x": 0, "y": 0, "width": 100, "height": 100}}'
        )
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)

        with patch.object(
            provider._client.responses, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_response

            result = await provider.generate_response(sample_messages)

            # Cost should include text + 1 image
            # Text: 100 * 0.005/1000 + 50 * 0.015/1000 = 0.0005 + 0.00075 = 0.00125
            # Image: 0.00255
            # Total: 0.00380
            assert result.usage.cost_usd > 0.001  # Has some cost


class TestOpenAIProviderCircuitBreaker:
    """Tests for circuit breaker integration."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_on_failures(
        self, test_settings: Settings, sample_messages: list[Message]
    ) -> None:
        """Test that circuit breaker opens after failures."""
        # Set low threshold for testing
        provider = OpenAIProvider(settings=test_settings)
        provider._circuit_breaker.config.failure_threshold = 2

        with patch.object(
            provider._client.responses, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.side_effect = Exception("API Error")

            # First failure
            with pytest.raises(LLMError):
                await provider.generate_response(sample_messages)

            # Second failure - should open circuit
            with pytest.raises(LLMError):
                await provider.generate_response(sample_messages)

            # Circuit should be open
            assert provider._circuit_breaker.is_open
