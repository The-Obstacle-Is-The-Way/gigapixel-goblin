"""Tests for giant.llm.converters module."""

import base64
from io import BytesIO

import pytest
from PIL import Image

from giant.llm.converters import (
    count_image_pixels_in_messages,
    count_images_in_messages,
    get_system_prompt_for_anthropic,
    get_system_prompt_for_openai,
    message_content_to_anthropic,
    message_content_to_openai,
    message_to_anthropic,
    message_to_openai,
    messages_to_anthropic,
    messages_to_openai_input,
)
from giant.llm.protocol import Message, MessageContent


class TestMessageContentToOpenai:
    """Tests for message_content_to_openai converter."""

    def test_text_content(self) -> None:
        """Test converting text content to OpenAI format."""
        content = MessageContent(type="text", text="Hello world")
        result = message_content_to_openai(content, role="user")
        assert result == {"type": "input_text", "text": "Hello world"}

    def test_assistant_text_content_uses_output_text(self) -> None:
        """Test converting assistant text content to OpenAI format."""
        content = MessageContent(type="text", text="Previous answer")
        result = message_content_to_openai(content, role="assistant")
        assert result == {"type": "output_text", "text": "Previous answer"}

    def test_image_content(self) -> None:
        """Test converting image content to OpenAI format."""
        content = MessageContent(
            type="image",
            image_base64="base64data...",
            media_type="image/jpeg",
        )
        result = message_content_to_openai(content, role="user")
        assert result == {
            "type": "input_image",
            "image_url": "data:image/jpeg;base64,base64data...",
        }

    def test_assistant_image_content_raises(self) -> None:
        """Test that assistant image content raises (unsupported)."""
        content = MessageContent(
            type="image",
            image_base64="base64data...",
            media_type="image/jpeg",
        )
        with pytest.raises(ValueError, match="only supports images in user messages"):
            message_content_to_openai(content, role="assistant")

    def test_text_without_text_field_raises(self) -> None:
        """Test that text content without text field raises."""
        content = MessageContent(type="text", text=None)
        with pytest.raises(ValueError, match="requires 'text' field"):
            message_content_to_openai(content, role="user")

    def test_image_without_base64_raises(self) -> None:
        """Test that image content without base64 raises."""
        content = MessageContent(type="image", image_base64=None)
        with pytest.raises(ValueError, match="requires 'image_base64' field"):
            message_content_to_openai(content, role="user")


class TestMessageToOpenai:
    """Tests for message_to_openai converter."""

    def test_user_message(self) -> None:
        """Test converting user message to OpenAI format."""
        message = Message(
            role="user",
            content=[MessageContent(type="text", text="Hello")],
        )
        result = message_to_openai(message)
        assert result["role"] == "user"
        assert result["content"] == [{"type": "input_text", "text": "Hello"}]

    def test_assistant_message_uses_output_text(self) -> None:
        """Test converting assistant message to OpenAI format."""
        message = Message(
            role="assistant",
            content=[MessageContent(type="text", text="Prior response")],
        )
        result = message_to_openai(message)
        assert result["role"] == "assistant"
        assert result["content"] == [{"type": "output_text", "text": "Prior response"}]

    def test_system_message(self) -> None:
        """Test converting system message to OpenAI format."""
        message = Message(
            role="system",
            content=[MessageContent(type="text", text="You are helpful.")],
        )
        result = message_to_openai(message)
        assert result["role"] == "system"
        assert result["content"] == "You are helpful."

    def test_multimodal_message(self) -> None:
        """Test converting multimodal message to OpenAI format."""
        message = Message(
            role="user",
            content=[
                MessageContent(type="text", text="Analyze this:"),
                MessageContent(type="image", image_base64="data..."),
            ],
        )
        result = message_to_openai(message)
        assert len(result["content"]) == 2
        assert result["content"][0]["type"] == "input_text"
        assert result["content"][1]["type"] == "input_image"


class TestMessagesToOpenaiInput:
    """Tests for messages_to_openai_input converter."""

    def test_filters_system_messages(self) -> None:
        """Test that system messages are filtered out."""
        messages = [
            Message(
                role="system", content=[MessageContent(type="text", text="System")]
            ),
            Message(role="user", content=[MessageContent(type="text", text="User")]),
        ]
        result = messages_to_openai_input(messages)
        # Only user message should be included
        assert len(result) == 1
        assert result[0]["role"] == "user"

    def test_preserves_order(self) -> None:
        """Test that message order is preserved."""
        messages = [
            Message(role="user", content=[MessageContent(type="text", text="First")]),
            Message(
                role="assistant", content=[MessageContent(type="text", text="Response")]
            ),
            Message(role="user", content=[MessageContent(type="text", text="Second")]),
        ]
        result = messages_to_openai_input(messages)
        assert len(result) == 3
        assert result[0]["role"] == "user"
        assert result[1]["role"] == "assistant"
        assert result[2]["role"] == "user"


class TestGetSystemPromptForOpenai:
    """Tests for get_system_prompt_for_openai function."""

    def test_extracts_system_prompt(self) -> None:
        """Test extracting system prompt from messages."""
        messages = [
            Message(
                role="system", content=[MessageContent(type="text", text="Prompt")]
            ),
            Message(role="user", content=[MessageContent(type="text", text="User")]),
        ]
        result = get_system_prompt_for_openai(messages)
        assert result == "Prompt"

    def test_combines_multiple_system_messages(self) -> None:
        """Test combining multiple system messages."""
        messages = [
            Message(
                role="system", content=[MessageContent(type="text", text="Part 1")]
            ),
            Message(
                role="system", content=[MessageContent(type="text", text="Part 2")]
            ),
        ]
        result = get_system_prompt_for_openai(messages)
        assert result == "Part 1\nPart 2"

    def test_returns_none_if_no_system(self) -> None:
        """Test returning None when no system messages."""
        messages = [
            Message(role="user", content=[MessageContent(type="text", text="User")]),
        ]
        result = get_system_prompt_for_openai(messages)
        assert result is None


class TestMessageContentToAnthropic:
    """Tests for message_content_to_anthropic converter."""

    def test_text_content(self) -> None:
        """Test converting text content to Anthropic format."""
        content = MessageContent(type="text", text="Hello world")
        result = message_content_to_anthropic(content)
        assert result == {"type": "text", "text": "Hello world"}

    def test_image_content(self) -> None:
        """Test converting image content to Anthropic format."""
        content = MessageContent(
            type="image",
            image_base64="base64data...",
            media_type="image/jpeg",
        )
        result = message_content_to_anthropic(content)
        assert result == {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": "base64data...",
            },
        }

    def test_text_without_text_field_raises(self) -> None:
        """Test that text content without text field raises."""
        content = MessageContent(type="text", text=None)
        with pytest.raises(ValueError, match="requires 'text' field"):
            message_content_to_anthropic(content)

    def test_image_without_base64_raises(self) -> None:
        """Test that image content without base64 raises."""
        content = MessageContent(type="image", image_base64=None)
        with pytest.raises(ValueError, match="requires 'image_base64' field"):
            message_content_to_anthropic(content)


class TestMessageToAnthropic:
    """Tests for message_to_anthropic converter."""

    def test_user_message(self) -> None:
        """Test converting user message to Anthropic format."""
        message = Message(
            role="user",
            content=[MessageContent(type="text", text="Hello")],
        )
        result = message_to_anthropic(message)
        assert result["role"] == "user"
        assert result["content"] == [{"type": "text", "text": "Hello"}]

    def test_system_message_raises(self) -> None:
        """Test that system messages raise ValueError."""
        message = Message(
            role="system",
            content=[MessageContent(type="text", text="System")],
        )
        with pytest.raises(ValueError, match="'system' parameter"):
            message_to_anthropic(message)


class TestMessagesToAnthropic:
    """Tests for messages_to_anthropic converter."""

    def test_filters_system_messages(self) -> None:
        """Test that system messages are filtered out."""
        messages = [
            Message(
                role="system", content=[MessageContent(type="text", text="System")]
            ),
            Message(role="user", content=[MessageContent(type="text", text="User")]),
        ]
        result = messages_to_anthropic(messages)
        assert len(result) == 1
        assert result[0]["role"] == "user"


class TestGetSystemPromptForAnthropic:
    """Tests for get_system_prompt_for_anthropic function."""

    def test_extracts_system_prompt(self) -> None:
        """Test extracting system prompt from messages."""
        messages = [
            Message(
                role="system", content=[MessageContent(type="text", text="Prompt")]
            ),
        ]
        result = get_system_prompt_for_anthropic(messages)
        assert result == "Prompt"

    def test_returns_none_if_no_system(self) -> None:
        """Test returning None when no system messages."""
        messages = [
            Message(role="user", content=[MessageContent(type="text", text="User")]),
        ]
        result = get_system_prompt_for_anthropic(messages)
        assert result is None


class TestCountImagesInMessages:
    """Tests for count_images_in_messages function."""

    def test_no_images(self) -> None:
        """Test counting when no images present."""
        messages = [
            Message(role="user", content=[MessageContent(type="text", text="Hello")]),
        ]
        assert count_images_in_messages(messages) == 0

    def test_single_image(self) -> None:
        """Test counting single image."""
        messages = [
            Message(
                role="user",
                content=[MessageContent(type="image", image_base64="data")],
            ),
        ]
        assert count_images_in_messages(messages) == 1

    def test_multiple_images(self) -> None:
        """Test counting multiple images across messages."""
        messages = [
            Message(
                role="user",
                content=[
                    MessageContent(type="text", text="First"),
                    MessageContent(type="image", image_base64="img1"),
                ],
            ),
            Message(
                role="user",
                content=[
                    MessageContent(type="image", image_base64="img2"),
                    MessageContent(type="image", image_base64="img3"),
                ],
            ),
        ]
        assert count_images_in_messages(messages) == 3


class TestCountImagePixelsInMessages:
    """Tests for count_image_pixels_in_messages function."""

    def test_counts_pixels_for_single_image(self) -> None:
        """Pixel count equals width * height for one image."""
        image = Image.new("RGB", (7, 9), color=(0, 0, 0))
        buf = BytesIO()
        image.save(buf, format="JPEG", quality=85)
        image_b64 = base64.b64encode(buf.getvalue()).decode("ascii")

        messages = [
            Message(
                role="user",
                content=[MessageContent(type="image", image_base64=image_b64)],
            )
        ]
        assert count_image_pixels_in_messages(messages) == 63

    def test_invalid_base64_raises(self) -> None:
        """Invalid base64 should raise ValueError."""
        messages = [
            Message(
                role="user",
                content=[MessageContent(type="image", image_base64="not-base64!!!")],
            )
        ]
        with pytest.raises(ValueError, match="Invalid base64"):
            count_image_pixels_in_messages(messages)
