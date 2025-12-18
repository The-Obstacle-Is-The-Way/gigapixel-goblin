"""Tests for giant.llm.protocol module."""

import pytest
from pydantic import ValidationError

from giant.llm.protocol import (
    BoundingBoxAction,
    CircuitBreakerOpenError,
    FinalAnswerAction,
    LLMError,
    LLMParseError,
    LLMResponse,
    Message,
    MessageContent,
    StepResponse,
    TokenUsage,
)


class TestBoundingBoxAction:
    """Tests for BoundingBoxAction model."""

    def test_valid_bounding_box(self) -> None:
        """Test creating a valid bounding box action."""
        action = BoundingBoxAction(x=100, y=200, width=300, height=400)
        assert action.action_type == "crop"
        assert action.x == 100
        assert action.y == 200
        assert action.width == 300
        assert action.height == 400

    def test_negative_coordinates_rejected(self) -> None:
        """Test that negative coordinates are rejected."""
        with pytest.raises(ValidationError):
            BoundingBoxAction(x=-1, y=0, width=100, height=100)

    def test_zero_width_rejected(self) -> None:
        """Test that zero width is rejected."""
        with pytest.raises(ValidationError):
            BoundingBoxAction(x=0, y=0, width=0, height=100)

    def test_zero_height_rejected(self) -> None:
        """Test that zero height is rejected."""
        with pytest.raises(ValidationError):
            BoundingBoxAction(x=0, y=0, width=100, height=0)

    def test_action_type_is_crop(self) -> None:
        """Test that action_type defaults to 'crop'."""
        action = BoundingBoxAction(x=0, y=0, width=100, height=100)
        assert action.action_type == "crop"


class TestFinalAnswerAction:
    """Tests for FinalAnswerAction model."""

    def test_valid_final_answer(self) -> None:
        """Test creating a valid final answer action."""
        action = FinalAnswerAction(answer_text="This is the diagnosis")
        assert action.action_type == "answer"
        assert action.answer_text == "This is the diagnosis"

    def test_empty_answer_rejected(self) -> None:
        """Test that empty answer text is rejected."""
        with pytest.raises(ValidationError):
            FinalAnswerAction(answer_text="")

    def test_action_type_is_answer(self) -> None:
        """Test that action_type defaults to 'answer'."""
        action = FinalAnswerAction(answer_text="Test")
        assert action.action_type == "answer"


class TestStepResponse:
    """Tests for StepResponse model."""

    def test_valid_step_response_with_crop(self) -> None:
        """Test creating step response with crop action."""
        action = BoundingBoxAction(x=10, y=20, width=100, height=100)
        response = StepResponse(
            reasoning="I see a suspicious region in the top-left",
            action=action,
        )
        assert response.reasoning == "I see a suspicious region in the top-left"
        assert response.action == action

    def test_valid_step_response_with_answer(self) -> None:
        """Test creating step response with answer action."""
        action = FinalAnswerAction(answer_text="Malignant tumor detected")
        response = StepResponse(
            reasoning="Based on cellular patterns",
            action=action,
        )
        assert response.reasoning == "Based on cellular patterns"
        assert response.action == action

    def test_empty_reasoning_rejected(self) -> None:
        """Test that empty reasoning is rejected."""
        action = BoundingBoxAction(x=0, y=0, width=100, height=100)
        with pytest.raises(ValidationError):
            StepResponse(reasoning="", action=action)

    def test_json_serialization_crop(self) -> None:
        """Test JSON serialization of crop action."""
        action = BoundingBoxAction(x=10, y=20, width=100, height=100)
        response = StepResponse(reasoning="Test", action=action)
        json_str = response.model_dump_json()
        assert '"action_type":"crop"' in json_str

    def test_json_deserialization_crop(self) -> None:
        """Test JSON deserialization of crop action."""
        json_str = (
            '{"reasoning": "Test", "action": '
            '{"action_type": "crop", "x": 10, "y": 20, "width": 100, "height": 100}}'
        )
        response = StepResponse.model_validate_json(json_str)
        assert isinstance(response.action, BoundingBoxAction)
        assert response.action.x == 10

    def test_json_deserialization_answer(self) -> None:
        """Test JSON deserialization of answer action."""
        json_str = (
            '{"reasoning": "Test", "action": '
            '{"action_type": "answer", "answer_text": "Result"}}'
        )
        response = StepResponse.model_validate_json(json_str)
        assert isinstance(response.action, FinalAnswerAction)
        assert response.action.answer_text == "Result"


class TestTokenUsage:
    """Tests for TokenUsage model."""

    def test_valid_token_usage(self) -> None:
        """Test creating valid token usage."""
        usage = TokenUsage(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost_usd=0.005,
        )
        assert usage.prompt_tokens == 100
        assert usage.completion_tokens == 50
        assert usage.total_tokens == 150
        assert usage.cost_usd == 0.005

    def test_negative_tokens_rejected(self) -> None:
        """Test that negative token counts are rejected."""
        with pytest.raises(ValidationError):
            TokenUsage(
                prompt_tokens=-1,
                completion_tokens=50,
                total_tokens=49,
                cost_usd=0.005,
            )

    def test_negative_cost_rejected(self) -> None:
        """Test that negative cost is rejected."""
        with pytest.raises(ValidationError):
            TokenUsage(
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150,
                cost_usd=-0.005,
            )


class TestMessageContent:
    """Tests for MessageContent model."""

    def test_text_content(self) -> None:
        """Test creating text content."""
        content = MessageContent(type="text", text="Hello world")
        assert content.type == "text"
        assert content.text == "Hello world"
        assert content.image_base64 is None

    def test_image_content(self) -> None:
        """Test creating image content."""
        content = MessageContent(
            type="image",
            image_base64="base64data...",
            media_type="image/jpeg",
        )
        assert content.type == "image"
        assert content.image_base64 == "base64data..."
        assert content.media_type == "image/jpeg"

    def test_default_media_type(self) -> None:
        """Test default media type is image/jpeg."""
        content = MessageContent(type="image", image_base64="data")
        assert content.media_type == "image/jpeg"


class TestMessage:
    """Tests for Message model."""

    def test_user_message(self) -> None:
        """Test creating a user message."""
        content = [MessageContent(type="text", text="What do you see?")]
        message = Message(role="user", content=content)
        assert message.role == "user"
        assert len(message.content) == 1

    def test_system_message(self) -> None:
        """Test creating a system message."""
        content = [MessageContent(type="text", text="You are a pathologist.")]
        message = Message(role="system", content=content)
        assert message.role == "system"

    def test_multimodal_message(self) -> None:
        """Test creating a message with text and image."""
        content = [
            MessageContent(type="text", text="Analyze this region:"),
            MessageContent(type="image", image_base64="base64data..."),
        ]
        message = Message(role="user", content=content)
        assert len(message.content) == 2
        assert message.content[0].type == "text"
        assert message.content[1].type == "image"


class TestLLMResponse:
    """Tests for LLMResponse model."""

    def test_valid_llm_response(self) -> None:
        """Test creating a valid LLM response."""
        step_response = StepResponse(
            reasoning="Test reasoning",
            action=BoundingBoxAction(x=0, y=0, width=100, height=100),
        )
        usage = TokenUsage(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost_usd=0.005,
        )
        response = LLMResponse(
            step_response=step_response,
            usage=usage,
            model="gpt-4o",
            latency_ms=500.0,
        )
        assert response.model == "gpt-4o"
        assert response.latency_ms == 500.0

    def test_negative_latency_rejected(self) -> None:
        """Test that negative latency is rejected."""
        step_response = StepResponse(
            reasoning="Test",
            action=BoundingBoxAction(x=0, y=0, width=100, height=100),
        )
        usage = TokenUsage(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost_usd=0.005,
        )
        with pytest.raises(ValidationError):
            LLMResponse(
                step_response=step_response,
                usage=usage,
                model="gpt-4o",
                latency_ms=-100.0,
            )


class TestLLMError:
    """Tests for LLMError exception."""

    def test_basic_error(self) -> None:
        """Test creating a basic LLM error."""
        error = LLMError("API call failed")
        assert "API call failed" in str(error)

    def test_error_with_metadata(self) -> None:
        """Test creating error with provider/model metadata."""
        error = LLMError(
            "Rate limited",
            provider="openai",
            model="gpt-4o",
        )
        assert error.provider == "openai"
        assert error.model == "gpt-4o"

    def test_error_with_cause(self) -> None:
        """Test creating error with cause exception."""
        cause = ValueError("Original error")
        error = LLMError("Wrapped error", cause=cause)
        assert error.cause == cause


class TestLLMParseError:
    """Tests for LLMParseError exception."""

    def test_parse_error(self) -> None:
        """Test creating a parse error."""
        error = LLMParseError(
            "Invalid JSON",
            raw_output="not json",
            provider="openai",
        )
        assert "Invalid JSON" in str(error)
        assert error.raw_output == "not json"


class TestCircuitBreakerOpenError:
    """Tests for CircuitBreakerOpenError exception."""

    def test_circuit_breaker_error(self) -> None:
        """Test creating a circuit breaker error."""
        error = CircuitBreakerOpenError(
            "Circuit is open",
            cooldown_remaining_seconds=30.5,
            provider="openai",
        )
        assert "Circuit is open" in str(error)
        assert error.cooldown_remaining_seconds == 30.5
        assert error.provider == "openai"
