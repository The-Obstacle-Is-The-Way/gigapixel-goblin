"""GIANT configuration using pydantic-settings.

All configuration is strongly typed and supports environment variables
and .env files.
"""

from pathlib import Path
from typing import TypeGuard

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PLACEHOLDER_SECRET_MARKERS: tuple[str, ...] = (
    "your-key",
    "changeme",
)


class ConfigError(Exception):
    """Raised when required configuration is missing or invalid.

    This exception provides clear, actionable error messages when
    configuration values required by a specific operation are not set.

    Example:
        >>> Settings(_env_file=None).require_openai_key()  # doctest: +ELLIPSIS
        Traceback (most recent call last):
        ...
        ConfigError: OpenAI API key not configured. Set it in .env file or
        OPENAI_API_KEY environment variable.
    """

    def __init__(self, key_name: str, env_var: str) -> None:
        """Initialize configuration error.

        Args:
            key_name: Human-readable name of the missing key.
            env_var: Environment variable name to set.
        """
        self.key_name = key_name
        self.env_var = env_var
        message = (
            f"{key_name} not configured. "
            f"Set it in .env file or {env_var} environment variable."
        )
        super().__init__(message)


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    # API Keys
    OPENAI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None
    GOOGLE_API_KEY: str | None = None  # Future: Gemini provider (P4)
    HUGGINGFACE_TOKEN: str | None = None

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "console"  # "console" or "json"

    # Paper Parameters (GIANT)
    WSI_LONG_SIDE_TARGET: int = 1000  # S parameter - crop target size
    MAX_ITERATIONS: int = 20  # T parameter - max navigation steps
    OVERSAMPLING_BIAS: float = 0.85  # Bias for larger crop sizes
    THUMBNAIL_SIZE: int = 1024  # Thumbnail long side for LMM context

    # Baselines
    PATCH_SIZE: int = 224  # Patch size for random sampling baseline
    PATCH_COUNT: int = 30  # Number of patches for baseline

    # Evaluation
    BOOTSTRAP_REPLICATES: int = 1000  # Paper uses 1000 for Table 1 stats

    # Image Generation
    JPEG_QUALITY: int = 85  # Quality for base64 encoding

    # Per-provider image sizes (paper uses 500px for Claude due to pricing)
    IMAGE_SIZE_OPENAI: int = 1000
    IMAGE_SIZE_ANTHROPIC: int = 500

    # Rate Limiting
    OPENAI_RPM: int = 60  # Requests per minute for OpenAI
    ANTHROPIC_RPM: int = 60  # Requests per minute for Anthropic

    # Budget Guardrails
    DEFAULT_BUDGET_USD: float = 0.0  # 0 = no budget limit

    # Prompt overrides (paper reproducibility / experimentation)
    # If set, these override the default system prompt in
    # `src/giant/prompts/templates.py`.
    # Use *_PATH for long prompts to avoid multi-line env vars.
    GIANT_SYSTEM_PROMPT: str | None = None
    GIANT_SYSTEM_PROMPT_PATH: str | None = None
    GIANT_SYSTEM_PROMPT_OPENAI: str | None = None
    GIANT_SYSTEM_PROMPT_OPENAI_PATH: str | None = None
    GIANT_SYSTEM_PROMPT_ANTHROPIC: str | None = None
    GIANT_SYSTEM_PROMPT_ANTHROPIC_PATH: str | None = None

    @model_validator(mode="after")
    def _apply_paper_parameter_overrides(self) -> "Settings":
        if "WSI_LONG_SIDE_TARGET" in self.model_fields_set:
            if "IMAGE_SIZE_OPENAI" not in self.model_fields_set:
                self.IMAGE_SIZE_OPENAI = self.WSI_LONG_SIDE_TARGET
            if "IMAGE_SIZE_ANTHROPIC" not in self.model_fields_set:
                self.IMAGE_SIZE_ANTHROPIC = self.WSI_LONG_SIDE_TARGET
        return self

    @staticmethod
    def _is_configured_secret(value: str | None) -> TypeGuard[str]:
        if value is None:
            return False

        stripped = value.strip()
        if stripped == "":
            return False

        lowered = stripped.lower()
        return not any(marker in lowered for marker in _PLACEHOLDER_SECRET_MARKERS)

    def require_openai_key(self) -> str:
        """Get OpenAI API key, raising ConfigError if not set.

        Use this method when making OpenAI API calls to get a clear error
        message instead of cryptic authentication failures.

        Returns:
            The OpenAI API key string.

        Raises:
            ConfigError: If OPENAI_API_KEY is not configured.
        """
        if not self._is_configured_secret(self.OPENAI_API_KEY):
            raise ConfigError("OpenAI API key", "OPENAI_API_KEY")
        return self.OPENAI_API_KEY

    def require_anthropic_key(self) -> str:
        """Get Anthropic API key, raising ConfigError if not set.

        Use this method when making Anthropic API calls to get a clear error
        message instead of cryptic authentication failures.

        Returns:
            The Anthropic API key string.

        Raises:
            ConfigError: If ANTHROPIC_API_KEY is not configured.
        """
        if not self._is_configured_secret(self.ANTHROPIC_API_KEY):
            raise ConfigError("Anthropic API key", "ANTHROPIC_API_KEY")
        return self.ANTHROPIC_API_KEY

    def require_google_key(self) -> str:
        """Get Google API key, raising ConfigError if not set.

        Use this method when making Google/Gemini API calls to get a clear
        error message instead of cryptic authentication failures.

        Note: GoogleProvider is P4 (future work). This method is scaffolded
        for consistency with other providers.

        Returns:
            The Google API key string.

        Raises:
            ConfigError: If GOOGLE_API_KEY is not configured.
        """
        if not self._is_configured_secret(self.GOOGLE_API_KEY):
            raise ConfigError("Google API key", "GOOGLE_API_KEY")
        return self.GOOGLE_API_KEY

    def require_huggingface_token(self) -> str:
        """Get HuggingFace token, raising ConfigError if not set.

        Use this method when accessing gated HuggingFace repositories
        to get a clear error message instead of auth failures.

        Returns:
            The HuggingFace token string.

        Raises:
            ConfigError: If HUGGINGFACE_TOKEN is not configured.
        """
        if not self._is_configured_secret(self.HUGGINGFACE_TOKEN):
            raise ConfigError("HuggingFace token", "HUGGINGFACE_TOKEN")
        return self.HUGGINGFACE_TOKEN

    @staticmethod
    def _read_prompt_file(path_str: str) -> str:
        try:
            return Path(path_str).expanduser().read_text(encoding="utf-8")
        except OSError as e:
            raise ValueError(
                f"Failed to read prompt file: {path_str!r}. "
                "Ensure the path exists and is readable."
            ) from e

    def get_giant_system_prompt(self, *, provider: str | None) -> str | None:
        """Return an optional system prompt override for GIANT.

        Precedence (highest to lowest):
        1) Provider-specific *_PATH
        2) Provider-specific text value
        3) Global *_PATH
        4) Global text value
        """
        provider_norm = provider.strip().lower() if provider else None

        candidates: list[tuple[str | None, str | None]] = []
        if provider_norm == "openai":
            candidates.append(
                (self.GIANT_SYSTEM_PROMPT_OPENAI_PATH, self.GIANT_SYSTEM_PROMPT_OPENAI)
            )
        elif provider_norm == "anthropic":
            candidates.append(
                (
                    self.GIANT_SYSTEM_PROMPT_ANTHROPIC_PATH,
                    self.GIANT_SYSTEM_PROMPT_ANTHROPIC,
                )
            )

        candidates.append((self.GIANT_SYSTEM_PROMPT_PATH, self.GIANT_SYSTEM_PROMPT))

        for path_str, prompt in candidates:
            if path_str:
                return self._read_prompt_file(path_str)
            if prompt:
                return prompt
        return None


# Singleton instance for import convenience
settings = Settings()
