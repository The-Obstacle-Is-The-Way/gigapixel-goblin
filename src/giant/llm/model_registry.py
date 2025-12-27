"""Approved LLM model identifiers for GIANT.

`docs/models/model-registry.md` is the documentation SSOT. This module is the
runtime enforcement point to prevent accidental use of legacy/unsupported
models.
"""

from __future__ import annotations

DEFAULT_OPENAI_MODEL: str = "gpt-5.2"
DEFAULT_ANTHROPIC_MODEL: str = "claude-sonnet-4-5-20250929"
DEFAULT_GOOGLE_MODEL: str = "gemini-3-pro-preview"

DEFAULT_MODELS_BY_PROVIDER: dict[str, str] = {
    "openai": DEFAULT_OPENAI_MODEL,
    "anthropic": DEFAULT_ANTHROPIC_MODEL,
    "google": DEFAULT_GOOGLE_MODEL,
}

OPENAI_MODELS: frozenset[str] = frozenset(
    {
        DEFAULT_OPENAI_MODEL,
    }
)

ANTHROPIC_MODELS: frozenset[str] = frozenset(
    {
        DEFAULT_ANTHROPIC_MODEL,
    }
)

GOOGLE_MODELS: frozenset[str] = frozenset(
    {
        DEFAULT_GOOGLE_MODEL,
    }
)

APPROVED_MODELS: frozenset[str] = OPENAI_MODELS | ANTHROPIC_MODELS | GOOGLE_MODELS

APPROVED_MODELS_BY_PROVIDER: dict[str, frozenset[str]] = {
    "openai": OPENAI_MODELS,
    "anthropic": ANTHROPIC_MODELS,
    "google": GOOGLE_MODELS,
}


def get_default_model(provider: str) -> str:
    """Return the default model id for a provider.

    Raises:
        ValueError: If provider is unknown.
    """
    try:
        return DEFAULT_MODELS_BY_PROVIDER[provider]
    except KeyError as e:
        raise ValueError(
            f"Unknown provider: {provider!r}. Supported providers: "
            + ", ".join(sorted(DEFAULT_MODELS_BY_PROVIDER))
        ) from e


def validate_model_id(model: str, *, provider: str | None = None) -> None:
    """Validate that `model` is approved (and matches `provider` if provided).

    Raises:
        ValueError: If the model is not approved.
    """
    if provider is None:
        allowed = APPROVED_MODELS
        label = "GIANT approved models"
    else:
        if provider not in APPROVED_MODELS_BY_PROVIDER:
            raise ValueError(
                f"Unknown provider: {provider!r}. Supported providers: "
                + ", ".join(sorted(APPROVED_MODELS_BY_PROVIDER))
            )
        allowed = APPROVED_MODELS_BY_PROVIDER[provider]
        label = f"{provider} approved models"

    if model not in allowed:
        allowed_list = ", ".join(sorted(allowed))
        raise ValueError(
            f"Model {model!r} is not approved. Allowed for {label}: {allowed_list}. "
            "See docs/models/model-registry.md."
        )
