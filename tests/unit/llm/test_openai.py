"Tests for giant.llm.openai_client module."

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from openai import APIConnectionError

from giant.config import Settings
from giant.llm.model_registry import DEFAULT_ANTHROPIC_MODEL, DEFAULT_OPENAI_MODEL
from giant.llm.openai_client import (
    OpenAIProvider,
    _build_json_schema,
    _normalize_openai_response,
)
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
        """Test that action schema has action_type discriminator.

        OpenAI doesn't support oneOf, so we use a flattened schema with
        all fields present (nullable for unused ones) and action_type
        as the discriminator.
        """
        schema = _build_json_schema()
        action_schema = schema["schema"]["properties"]["action"]

        # Verify flattened schema (no oneOf)
        assert "oneOf" not in action_schema
        assert action_schema["type"] == "object"

        # Verify action_type discriminator
        assert "action_type" in action_schema["properties"]
        assert action_schema["properties"]["action_type"]["enum"] == ["crop", "answer"]

        # Verify all fields are present (flattened union)
        props = action_schema["properties"]
        assert "x" in props
        assert "y" in props
        assert "width" in props
        assert "height" in props
        assert "answer_text" in props


class TestNormalizeOpenAIResponse:
    """Tests for _normalize_openai_response helper."""

    def test_crop_action_normalized(self) -> None:
        """Crop action is normalized correctly."""
        data = {
            "reasoning": "I see something",
            "action": {
                "action_type": "crop",
                "x": 100,
                "y": 200,
                "width": 50,
                "height": 50,
                "answer_text": None,  # OpenAI includes nulls
            },
        }
        result = _normalize_openai_response(data)
        assert result["action"]["action_type"] == "crop"
        assert "answer_text" not in result["action"]  # Null filtered out

    def test_answer_action_normalized(self) -> None:
        """Answer action is normalized correctly."""
        data = {
            "reasoning": "This is benign",
            "action": {
                "action_type": "answer",
                "answer_text": "Benign tissue",
                "x": None,
                "y": None,
                "width": None,
                "height": None,
            },
        }
        result = _normalize_openai_response(data)
        assert result["action"]["action_type"] == "answer"
        assert result["action"]["answer_text"] == "Benign tissue"
        assert "x" not in result["action"]  # Null filtered out

    def test_unknown_action_type_raises_clear_error(self) -> None:
        """Unknown action_type raises LLMParseError with clear message (BUG-038-B10)."""
        data = {
            "reasoning": "I want to zoom",
            "action": {
                "action_type": "zoom",  # Unknown
                "level": 2,
            },
        }
        with pytest.raises(LLMParseError) as exc_info:
            _normalize_openai_response(data)

        assert "Unknown action_type" in str(exc_info.value)
        assert "zoom" in str(exc_info.value)
        assert "crop" in str(exc_info.value) or "answer" in str(exc_info.value)

    def test_none_action_type_raises_clear_error(self) -> None:
        """None action_type raises LLMParseError."""
        data = {
            "reasoning": "No action",
            "action": {
                "action_type": None,
            },
        }
        with pytest.raises(LLMParseError) as exc_info:
            _normalize_openai_response(data)

        assert "Unknown action_type" in str(exc_info.value)

    def test_missing_action_type_raises_clear_error(self) -> None:
        """Missing action_type raises LLMParseError."""
        data = {
            "reasoning": "Bad action",
            "action": {
                "x": 100,  # No action_type
            },
        }
        with pytest.raises(LLMParseError) as exc_info:
            _normalize_openai_response(data)

        assert "Unknown action_type" in str(exc_info.value)

    def test_missing_action_key_returns_data(self) -> None:
        """Missing 'action' key passes through (let pydantic handle)."""
        data = {"reasoning": "No action key"}
        result = _normalize_openai_response(data)
        assert result == data

    def test_non_dict_action_returns_data(self) -> None:
        """Non-dict action passes through (let pydantic handle)."""
        data = {"reasoning": "Bad action", "action": "not a dict"}
        result = _normalize_openai_response(data)
        assert result == data


class TestOpenAIProviderInit:
    """Tests for OpenAIProvider initialization."""

    def test_init_with_default_model(self, test_settings: Settings) -> None:
        """Test initialization with default model."""
        provider = OpenAIProvider(settings=test_settings)
        assert provider.model == DEFAULT_OPENAI_MODEL
        assert provider.get_model_name() == DEFAULT_OPENAI_MODEL

    def test_init_with_invalid_model_raises(self, test_settings: Settings) -> None:
        """Test initialization rejects non-OpenAI approved models."""
        with pytest.raises(ValueError):
            OpenAIProvider(model=DEFAULT_ANTHROPIC_MODEL, settings=test_settings)

    def test_get_target_size(self, test_settings: Settings) -> None:
        """Test target size from settings."""
        provider = OpenAIProvider(settings=test_settings)
        assert provider.get_target_size() == 1000


class TestOpenAIProviderGenerate:
    """Tests for OpenAIProvider.generate_response."""

    @pytest.mark.asyncio
    async def test_successful_crop_response(
        self,
        test_settings: Settings,
        sample_messages: list[Message],
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
            assert result.model == DEFAULT_OPENAI_MODEL
            assert result.latency_ms > 0

    @pytest.mark.asyncio
    async def test_successful_answer_response(
        self,
        test_settings: Settings,
        sample_messages: list[Message],
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
        self,
        test_settings: Settings,
        sample_messages: list[Message],
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

    # BUG-038 B2: JSON with trailing text should parse successfully
    @pytest.mark.asyncio
    async def test_parse_response_with_trailing_text(
        self,
        test_settings: Settings,
        sample_messages: list[Message],
    ) -> None:
        """JSON with trailing text should parse successfully (BUG-038 B2)."""
        provider = OpenAIProvider(settings=test_settings)

        mock_response = MagicMock()
        # LLM sometimes adds explanatory text after JSON
        mock_response.output_text = (
            '{"reasoning": "Based on analysis", '
            '"action": {"action_type": "answer", "answer_text": "Benign"}}'
            " I hope this helps explain my reasoning."
        )
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)

        with patch.object(
            provider._client.responses, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_response

            # Should NOT raise - trailing text should be ignored
            result = await provider.generate_response(sample_messages)

            assert result.step_response.reasoning == "Based on analysis"
            assert result.step_response.action.action_type == "answer"
            assert result.step_response.action.answer_text == "Benign"

    @pytest.mark.asyncio
    async def test_parse_response_with_newlines_and_trailing(
        self,
        test_settings: Settings,
        sample_messages: list[Message],
    ) -> None:
        """JSON with newlines and trailing text should parse (BUG-038 B2)."""
        provider = OpenAIProvider(settings=test_settings)

        mock_response = MagicMock()
        mock_response.output_text = (
            '{"reasoning": "test", "action": {"action_type": "crop", '
            '"x": 100, "y": 200, "width": 50, "height": 50}}\n\n'
            "Let me know if you need more info."
        )
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)

        with patch.object(
            provider._client.responses, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_response

            result = await provider.generate_response(sample_messages)

            assert result.step_response.action.action_type == "crop"
            assert result.step_response.action.x == 100

    @pytest.mark.asyncio
    async def test_parse_response_with_leading_whitespace_and_trailing(
        self,
        test_settings: Settings,
        sample_messages: list[Message],
    ) -> None:
        """Leading whitespace + trailing text should parse (BUG-038 B2)."""
        provider = OpenAIProvider(settings=test_settings)

        mock_response = MagicMock()
        mock_response.output_text = (
            "\n  "
            '{"reasoning": "ws", "action": {"action_type": "answer", '
            '"answer_text": "ok"}} trailing'
        )
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)

        with patch.object(
            provider._client.responses, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_response

            result = await provider.generate_response(sample_messages)

            assert result.step_response.reasoning == "ws"
            assert result.step_response.action.action_type == "answer"
            assert result.step_response.action.answer_text == "ok"

    @pytest.mark.asyncio
    async def test_parse_error_on_missing_output(
        self,
        test_settings: Settings,
        sample_messages: list[Message],
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
    async def test_parse_error_on_empty_output_text(
        self,
        test_settings: Settings,
        sample_messages: list[Message],
    ) -> None:
        """Empty output text should raise a clear LLMParseError."""
        provider = OpenAIProvider(settings=test_settings)

        mock_response = MagicMock()
        mock_response.output_text = "   "
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)

        with patch.object(
            provider._client.responses, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_response

            with pytest.raises(LLMParseError) as exc_info:
                await provider.generate_response(sample_messages)

            assert "Empty output text" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_cost_calculation_includes_images(
        self,
        test_settings: Settings,
        sample_messages: list[Message],
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
            # Text: 100 * 0.00175/1000 + 50 * 0.014/1000 = 0.000175 + 0.0007 = 0.000875
            # Image: 0.00255
            # Total: 0.003425
            assert result.usage.cost_usd > 0.001  # Has some cost


class TestOpenAIProviderCircuitBreaker:
    """Tests for circuit breaker integration."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_on_failures(
        self,
        test_settings: Settings,
        sample_messages: list[Message],
    ) -> None:
        """Test that circuit breaker opens after transient failures.

        Only transient errors (RateLimitError, APIConnectionError) should
        trip the circuit breaker - not application bugs.
        """
        # Set low threshold for testing
        provider = OpenAIProvider(settings=test_settings)
        provider._circuit_breaker.config.failure_threshold = 2

        with patch.object(
            provider._client.responses, "create", new_callable=AsyncMock
        ) as mock_create:
            # Use APIConnectionError - a transient error that should trip breaker
            mock_create.side_effect = APIConnectionError(request=None)

            # First failure
            with pytest.raises(LLMError):
                await provider.generate_response(sample_messages)

            # Second failure - should open circuit
            with pytest.raises(LLMError):
                await provider.generate_response(sample_messages)

            # Circuit should be open
            assert provider._circuit_breaker.is_open


class TestOpenAITokenCounting:
    """Tests for token count edge cases."""

    @pytest.fixture
    def provider(self, test_settings) -> OpenAIProvider:
        """Create provider for testing."""
        return OpenAIProvider(settings=test_settings)

    @pytest.mark.asyncio
    async def test_none_input_tokens_raises_clear_llm_error(
        self, provider: OpenAIProvider, sample_messages
    ) -> None:
        """None input_tokens should raise clear LLMError (BUG-038-B5)."""
        mock_response = MagicMock()
        mock_response.output_text = (
            '{"reasoning": "test", "action": {'
            '"action_type": "answer", "answer_text": "ok"}}'
        )
        mock_response.usage = MagicMock()
        mock_response.usage.input_tokens = None  # Edge case
        mock_response.usage.output_tokens = 50

        with patch.object(
            provider._client.responses, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_response

            with pytest.raises(LLMError, match="None token counts"):
                await provider.generate_response(sample_messages)

    @pytest.mark.asyncio
    async def test_none_output_tokens_raises_clear_llm_error(
        self, provider: OpenAIProvider, sample_messages
    ) -> None:
        """None output_tokens should raise clear LLMError (BUG-038-B5)."""
        mock_response = MagicMock()
        mock_response.output_text = (
            '{"reasoning": "test", "action": {'
            '"action_type": "answer", "answer_text": "ok"}}'
        )
        mock_response.usage = MagicMock()
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = None  # Edge case

        with patch.object(
            provider._client.responses, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_response

            with pytest.raises(LLMError, match="None token counts"):
                await provider.generate_response(sample_messages)

    @pytest.mark.asyncio
    async def test_both_tokens_none_raises_clear_llm_error(
        self, provider: OpenAIProvider, sample_messages
    ) -> None:
        """Both tokens None should raise clear LLMError (BUG-038-B5)."""
        mock_response = MagicMock()
        mock_response.output_text = (
            '{"reasoning": "test", "action": {'
            '"action_type": "answer", "answer_text": "ok"}}'
        )
        mock_response.usage = MagicMock()
        mock_response.usage.input_tokens = None
        mock_response.usage.output_tokens = None

        with patch.object(
            provider._client.responses, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_response

            with pytest.raises(LLMError, match="None token counts"):
                await provider.generate_response(sample_messages)
