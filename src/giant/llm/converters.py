"""Message format converters for different LLM providers.

This module provides helper functions to convert the generic Message format
used throughout GIANT into provider-specific API payloads.

Each provider has its own format for multimodal content:
- OpenAI (Responses API): Uses role-specific content types
  - user: input_text, input_image
  - assistant: output_text, refusal
- Anthropic: Uses text and image types with base64 source
"""

from __future__ import annotations

import base64
import binascii
from io import BytesIO
from typing import Any, Literal

from PIL import Image

from giant.llm.protocol import Message, MessageContent


def message_content_to_openai(
    content: MessageContent,
    *,
    role: Literal["user", "assistant"],
) -> dict[str, Any]:
    """Convert MessageContent to OpenAI Responses API format.

    Args:
        content: Generic message content.
        role: Message role (user or assistant).

    Returns:
        OpenAI-formatted content dictionary.

    Raises:
        ValueError: If content type is invalid or missing required fields.
    """
    if content.type == "text":
        if content.text is None:
            raise ValueError("Text content requires 'text' field")
        return {
            "type": "output_text" if role == "assistant" else "input_text",
            "text": content.text,
        }
    elif content.type == "image":
        if role != "user":
            raise ValueError(
                "OpenAI Responses API only supports images in user messages"
            )
        if content.image_base64 is None:
            raise ValueError("Image content requires 'image_base64' field")
        return {
            "type": "input_image",
            "image_url": f"data:{content.media_type};base64,{content.image_base64}",
        }
    else:
        raise ValueError(f"Unknown content type: {content.type}")


def message_to_openai(message: Message) -> dict[str, Any]:
    """Convert Message to OpenAI Responses API format.

    Args:
        message: Generic message.

    Returns:
        OpenAI-formatted message dictionary.
    """
    # OpenAI Responses API uses "input" instead of "messages"
    # For system messages, we use a different structure
    if message.role == "system":
        # System messages are typically just text
        text_parts = [c.text for c in message.content if c.type == "text" and c.text]
        return {
            "role": "system",
            "content": "\n".join(text_parts),
        }

    return {
        "role": message.role,
        "content": [
            message_content_to_openai(c, role=message.role) for c in message.content
        ],
    }


def messages_to_openai_input(messages: list[Message]) -> list[dict[str, Any]]:
    """Convert a list of messages to OpenAI Responses API input format.

    The Responses API expects a flat list of input items.

    Args:
        messages: List of generic messages.

    Returns:
        List of OpenAI-formatted input items.
    """
    result: list[dict[str, Any]] = []

    for message in messages:
        if message.role == "system":
            # System messages handled separately in API call
            continue
        result.append(message_to_openai(message))

    return result


def get_system_prompt_for_openai(messages: list[Message]) -> str | None:
    """Extract system prompt from messages for OpenAI.

    Args:
        messages: List of generic messages.

    Returns:
        Combined system prompt text, or None if no system messages.
    """
    system_parts: list[str] = []
    for message in messages:
        if message.role == "system":
            for content in message.content:
                if content.type == "text" and content.text:
                    system_parts.append(content.text)

    return "\n".join(system_parts) if system_parts else None


def message_content_to_anthropic(content: MessageContent) -> dict[str, Any]:
    """Convert MessageContent to Anthropic API format.

    Args:
        content: Generic message content.

    Returns:
        Anthropic-formatted content dictionary.

    Raises:
        ValueError: If content type is invalid or missing required fields.
    """
    if content.type == "text":
        if content.text is None:
            raise ValueError("Text content requires 'text' field")
        return {
            "type": "text",
            "text": content.text,
        }
    elif content.type == "image":
        if content.image_base64 is None:
            raise ValueError("Image content requires 'image_base64' field")
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": content.media_type,
                "data": content.image_base64,
            },
        }
    else:
        raise ValueError(f"Unknown content type: {content.type}")


def message_to_anthropic(message: Message) -> dict[str, Any]:
    """Convert Message to Anthropic API format.

    Args:
        message: Generic message.

    Returns:
        Anthropic-formatted message dictionary.

    Note:
        System messages should be passed via the 'system' parameter
        in the API call, not as messages. This function will raise
        for system messages.

    Raises:
        ValueError: If message role is 'system'.
    """
    if message.role == "system":
        raise ValueError(
            "System messages should be passed via 'system' parameter, "
            "not as messages. Use get_system_prompt_for_anthropic()."
        )

    return {
        "role": message.role,
        "content": [message_content_to_anthropic(c) for c in message.content],
    }


def messages_to_anthropic(messages: list[Message]) -> list[dict[str, Any]]:
    """Convert messages to Anthropic API format.

    Filters out system messages (which should be passed separately).

    Args:
        messages: List of generic messages.

    Returns:
        List of Anthropic-formatted messages (excluding system).
    """
    return [message_to_anthropic(m) for m in messages if m.role != "system"]


def get_system_prompt_for_anthropic(messages: list[Message]) -> str | None:
    """Extract system prompt from messages for Anthropic.

    Args:
        messages: List of generic messages.

    Returns:
        Combined system prompt text, or None if no system messages.
    """
    system_parts: list[str] = []
    for message in messages:
        if message.role == "system":
            for content in message.content:
                if content.type == "text" and content.text:
                    system_parts.append(content.text)

    return "\n".join(system_parts) if system_parts else None


def count_images_in_messages(messages: list[Message]) -> int:
    """Count the number of images in a message list.

    Useful for cost calculation with OpenAI.

    Args:
        messages: List of messages.

    Returns:
        Total number of image content items.
    """
    count = 0
    for message in messages:
        for content in message.content:
            if content.type == "image":
                count += 1
    return count


def count_image_pixels_in_messages(messages: list[Message]) -> int:
    """Count total pixels across all images in a message list.

    Useful for Anthropic cost calculation, which is pixel-based.

    Raises:
        ValueError: If any image_base64 is invalid or not decodable as an image.
    """
    total_pixels = 0
    for message in messages:
        for content in message.content:
            if content.type != "image":
                continue
            if content.image_base64 is None:
                raise ValueError("Image content requires 'image_base64' field")
            if content.image_base64 == "":
                raise ValueError("Image content has empty 'image_base64' field")
            try:
                image_bytes = base64.b64decode(content.image_base64, validate=True)
            except binascii.Error as e:
                raise ValueError("Invalid base64 image data") from e
            if not image_bytes:
                raise ValueError("Image base64 decoded to empty bytes")
            with Image.open(BytesIO(image_bytes)) as image:
                width, height = image.size
            total_pixels += width * height
    return total_pixels
