"""Shared pytest fixtures and configuration."""

from collections.abc import Iterator
from typing import Any

import pytest

from giant.config import Settings
from giant.utils.logging import clear_correlation_context, configure_logging


@pytest.fixture(autouse=True)
def reset_logging_context() -> Iterator[None]:
    """Reset correlation context between tests."""
    clear_correlation_context()
    yield
    clear_correlation_context()


@pytest.fixture
def test_settings() -> Settings:
    """Create a Settings instance with test-safe defaults."""
    return Settings(
        OPENAI_API_KEY="test-openai-key",
        ANTHROPIC_API_KEY="test-anthropic-key",
        HUGGINGFACE_TOKEN="test-hf-token",
        LOG_LEVEL="DEBUG",
        LOG_FORMAT="console",
    )


@pytest.fixture
def configure_test_logging() -> Iterator[None]:
    """Configure logging for tests with console output."""
    configure_logging(level="DEBUG", log_format="console")
    yield


@pytest.fixture
def mock_api_responses() -> dict[str, Any]:
    """Provide mock API response structures for LLM tests."""
    return {
        "openai_completion": {
            "id": "test-completion-id",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Test response",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
            },
        },
        "anthropic_message": {
            "id": "test-message-id",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "Test response"}],
            "stop_reason": "end_turn",
            "usage": {
                "input_tokens": 100,
                "output_tokens": 50,
            },
        },
    }
