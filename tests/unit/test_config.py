"""Tests for giant.config module."""

import pytest

from giant.config import ConfigError, Settings


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


class TestConfigError:
    """Tests for the ConfigError exception."""

    def test_config_error_message_format(self) -> None:
        """Test ConfigError message includes key name and env var."""
        error = ConfigError("OpenAI API key", "OPENAI_API_KEY")
        assert "OpenAI API key" in str(error)
        assert "OPENAI_API_KEY" in str(error)
        assert ".env" in str(error)

    def test_config_error_attributes(self) -> None:
        """Test ConfigError stores key name and env var as attributes."""
        error = ConfigError("Test key", "TEST_VAR")
        assert error.key_name == "Test key"
        assert error.env_var == "TEST_VAR"


class TestRequireMethods:
    """Tests for require_*_key() methods."""

    def test_require_openai_key_when_set(self) -> None:
        """Test require_openai_key returns key when set."""
        settings = Settings(
            OPENAI_API_KEY="sk-test-key",
            _env_file=None,  # type: ignore[call-arg]
        )
        result = settings.require_openai_key()
        assert result == "sk-test-key"

    def test_require_openai_key_when_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test require_openai_key raises ConfigError when not set."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
        )
        with pytest.raises(ConfigError) as exc_info:
            settings.require_openai_key()
        assert "OPENAI_API_KEY" in str(exc_info.value)

    def test_require_anthropic_key_when_set(self) -> None:
        """Test require_anthropic_key returns key when set."""
        settings = Settings(
            ANTHROPIC_API_KEY="sk-ant-test-key",
            _env_file=None,  # type: ignore[call-arg]
        )
        result = settings.require_anthropic_key()
        assert result == "sk-ant-test-key"

    def test_require_anthropic_key_when_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test require_anthropic_key raises ConfigError when not set."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
        )
        with pytest.raises(ConfigError) as exc_info:
            settings.require_anthropic_key()
        assert "ANTHROPIC_API_KEY" in str(exc_info.value)

    def test_require_huggingface_token_when_set(self) -> None:
        """Test require_huggingface_token returns token when set."""
        settings = Settings(
            HUGGINGFACE_TOKEN="hf_test_token",
            _env_file=None,  # type: ignore[call-arg]
        )
        result = settings.require_huggingface_token()
        assert result == "hf_test_token"

    def test_require_huggingface_token_when_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test require_huggingface_token raises ConfigError when not set."""
        monkeypatch.delenv("HUGGINGFACE_TOKEN", raising=False)
        settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
        )
        with pytest.raises(ConfigError) as exc_info:
            settings.require_huggingface_token()
        assert "HUGGINGFACE_TOKEN" in str(exc_info.value)

    def test_require_google_key_when_set(self) -> None:
        """Test require_google_key returns key when set."""
        settings = Settings(
            GOOGLE_API_KEY="google-test-key",
            _env_file=None,  # type: ignore[call-arg]
        )
        result = settings.require_google_key()
        assert result == "google-test-key"

    def test_require_google_key_when_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test require_google_key raises ConfigError when not set."""
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
        )
        with pytest.raises(ConfigError) as exc_info:
            settings.require_google_key()
        assert "GOOGLE_API_KEY" in str(exc_info.value)

    @pytest.mark.parametrize(
        ("settings_kwargs", "method_name", "expected_env_var"),
        [
            ({"OPENAI_API_KEY": ""}, "require_openai_key", "OPENAI_API_KEY"),
            ({"OPENAI_API_KEY": "   "}, "require_openai_key", "OPENAI_API_KEY"),
            (
                {"OPENAI_API_KEY": "your-key-here"},
                "require_openai_key",
                "OPENAI_API_KEY",
            ),
            ({"ANTHROPIC_API_KEY": ""}, "require_anthropic_key", "ANTHROPIC_API_KEY"),
            (
                {"ANTHROPIC_API_KEY": "   "},
                "require_anthropic_key",
                "ANTHROPIC_API_KEY",
            ),
            (
                {"ANTHROPIC_API_KEY": "your-key-here"},
                "require_anthropic_key",
                "ANTHROPIC_API_KEY",
            ),
            ({"GOOGLE_API_KEY": ""}, "require_google_key", "GOOGLE_API_KEY"),
            ({"GOOGLE_API_KEY": "   "}, "require_google_key", "GOOGLE_API_KEY"),
            (
                {"HUGGINGFACE_TOKEN": ""},
                "require_huggingface_token",
                "HUGGINGFACE_TOKEN",
            ),
            (
                {"HUGGINGFACE_TOKEN": "   "},
                "require_huggingface_token",
                "HUGGINGFACE_TOKEN",
            ),
        ],
    )
    def test_require_methods_reject_blank_values(
        self,
        settings_kwargs: dict[str, str],
        method_name: str,
        expected_env_var: str,
    ) -> None:
        """require_* methods reject empty/placeholder values."""
        settings = Settings(
            **settings_kwargs,
            _env_file=None,  # type: ignore[call-arg]
        )

        method = getattr(settings, method_name)
        with pytest.raises(ConfigError) as exc_info:
            method()
        assert expected_env_var in str(exc_info.value)
