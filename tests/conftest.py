"""Shared pytest fixtures and configuration."""

from collections.abc import Iterator

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


@pytest.fixture(autouse=True, scope="session")
def configure_test_logging() -> Iterator[None]:
    """Configure logging for tests with console output."""
    configure_logging(level="DEBUG", log_format="console")
    yield
