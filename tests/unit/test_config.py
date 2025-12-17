"""Tests for giant.config module."""

import pytest

from giant.config import Settings

# ruff: noqa: PLR2004  # Magic value comparisons are fine in tests


class TestSettings:
    """Tests for the Settings class."""

    def test_default_values(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that default values are set correctly."""
        # Clear any env vars that might be set
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("HUGGINGFACE_TOKEN", raising=False)

        # Create settings without any env vars
        settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
        )

        # API keys should be None by default (when not in env)
        assert settings.OPENAI_API_KEY is None
        assert settings.ANTHROPIC_API_KEY is None
        assert settings.HUGGINGFACE_TOKEN is None

        # Paper parameters should match spec
        assert settings.WSI_LONG_SIDE_TARGET == 1000  # S parameter
        assert settings.MAX_ITERATIONS == 20  # T parameter
        assert settings.OVERSAMPLING_BIAS == 0.85
        assert settings.THUMBNAIL_SIZE == 1024

        # Baselines
        assert settings.PATCH_SIZE == 224
        assert settings.PATCH_COUNT == 30

        # Evaluation
        assert settings.BOOTSTRAP_REPLICATES == 1000

        # Image settings
        assert settings.JPEG_QUALITY == 85
        assert settings.IMAGE_SIZE_OPENAI == 1000
        assert settings.IMAGE_SIZE_ANTHROPIC == 500

    def test_env_var_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that environment variables override defaults."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("MAX_ITERATIONS", "30")

        settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
        )

        assert settings.OPENAI_API_KEY == "sk-test-key"
        assert settings.LOG_LEVEL == "DEBUG"
        assert settings.MAX_ITERATIONS == 30

    def test_log_level_default(self) -> None:
        """Test that LOG_LEVEL defaults to INFO."""
        settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
        )
        assert settings.LOG_LEVEL == "INFO"

    def test_log_format_options(self) -> None:
        """Test that LOG_FORMAT accepts valid options."""
        settings = Settings(
            LOG_FORMAT="json",
            _env_file=None,  # type: ignore[call-arg]
        )
        assert settings.LOG_FORMAT == "json"

        settings = Settings(
            LOG_FORMAT="console",
            _env_file=None,  # type: ignore[call-arg]
        )
        assert settings.LOG_FORMAT == "console"

    def test_rate_limiting_defaults(self) -> None:
        """Test rate limiting default values."""
        settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
        )
        assert settings.OPENAI_RPM == 60
        assert settings.ANTHROPIC_RPM == 60

    def test_budget_guardrails_default(self) -> None:
        """Test budget guardrails default to disabled (0)."""
        settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
        )
        assert settings.DEFAULT_BUDGET_USD == 0.0

    def test_settings_immutability_after_creation(
        self, test_settings: Settings
    ) -> None:
        """Test that settings can be created with custom values."""
        assert test_settings.OPENAI_API_KEY == "test-openai-key"
        assert test_settings.LOG_LEVEL == "DEBUG"
