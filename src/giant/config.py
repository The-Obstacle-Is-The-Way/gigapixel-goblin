"""GIANT configuration using pydantic-settings.

All configuration is strongly typed and supports environment variables
and .env files.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


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
    HUGGINGFACE_TOKEN: str | None = None

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "console"  # "console" or "json"

    # Paper Parameters (from arXiv:2501.15257)
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


# Singleton instance for import convenience
settings = Settings()
