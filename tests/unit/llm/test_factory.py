"""Tests for giant.llm factory function."""

import pytest

from giant.config import Settings
from giant.llm import (
    AnthropicProvider,
    OpenAIProvider,
    create_provider,
)


@pytest.fixture
def mock_settings() -> Settings:
    """Create mock settings with API keys."""
    return Settings(
        OPENAI_API_KEY="test-openai-key",
        ANTHROPIC_API_KEY="test-anthropic-key",
        _env_file=None,  # type: ignore[call-arg]
    )


@pytest.fixture
def mock_providers(mock_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock the global settings used by providers."""
    # Patch the settings singleton
    monkeypatch.setattr("giant.llm.openai_client.settings", mock_settings)
    monkeypatch.setattr("giant.llm.anthropic_client.settings", mock_settings)


class TestCreateProvider:
    """Tests for create_provider factory function."""

    def test_create_openai_provider(self, mock_providers: None) -> None:
        """Test creating OpenAI provider."""
        provider = create_provider("openai")
        assert isinstance(provider, OpenAIProvider)
        assert provider.get_model_name() == "gpt-5.2"

    def test_create_openai_with_anthropic_model_rejected(
        self, mock_providers: None
    ) -> None:
        """Test OpenAI provider rejects non-OpenAI approved models."""
        with pytest.raises(ValueError) as exc_info:
            create_provider("openai", model="claude-opus-4-5-20251101")
        assert "not approved" in str(exc_info.value).lower()

    def test_create_anthropic_provider(self, mock_providers: None) -> None:
        """Test creating Anthropic provider."""
        provider = create_provider("anthropic")
        assert isinstance(provider, AnthropicProvider)
        assert provider.get_model_name() == "claude-opus-4-5-20251101"

    def test_create_anthropic_with_openai_model_rejected(
        self, mock_providers: None
    ) -> None:
        """Test Anthropic provider rejects non-Anthropic approved models."""
        with pytest.raises(ValueError) as exc_info:
            create_provider("anthropic", model="gpt-5.2")
        assert "not approved" in str(exc_info.value).lower()

    def test_unknown_provider_raises(self) -> None:
        """Test that unknown provider raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            create_provider("unknown")
        assert "Unknown provider" in str(exc_info.value)
        assert "openai" in str(exc_info.value)
        assert "anthropic" in str(exc_info.value)


class TestProviderTargetSizes:
    """Tests for provider target sizes."""

    def test_openai_target_size(self, mock_providers: None) -> None:
        """Test OpenAI provider returns correct target size."""
        provider = create_provider("openai")
        assert provider.get_target_size() == 1000

    def test_anthropic_target_size(self, mock_providers: None) -> None:
        """Test Anthropic provider returns correct target size."""
        provider = create_provider("anthropic")
        assert provider.get_target_size() == 500
