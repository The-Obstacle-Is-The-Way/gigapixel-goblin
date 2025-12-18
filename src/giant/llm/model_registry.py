"""Approved LLM model identifiers for GIANT.

`docs/models/MODEL_REGISTRY.md` is the documentation SSOT. This module is the
runtime enforcement point to prevent accidental use of legacy/unsupported
models.
"""

from __future__ import annotations

OPENAI_MODELS: frozenset[str] = frozenset(
    {
        "gpt-5.2-2025-12-11",
    }
)

ANTHROPIC_MODELS: frozenset[str] = frozenset(
    {
        "claude-opus-4-5-20251101",
    }
)

GOOGLE_MODELS: frozenset[str] = frozenset(
    {
        "gemini-3-pro-preview",
    }
)

APPROVED_MODELS: frozenset[str] = OPENAI_MODELS | ANTHROPIC_MODELS | GOOGLE_MODELS

APPROVED_MODELS_BY_PROVIDER: dict[str, frozenset[str]] = {
    "openai": OPENAI_MODELS,
    "anthropic": ANTHROPIC_MODELS,
    "google": GOOGLE_MODELS,
}


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
            "See docs/models/MODEL_REGISTRY.md."
        )
