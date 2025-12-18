"""LLM pricing and cost calculation for GIANT.

This module provides token-based cost calculation for different LLM providers
and models. Pricing is maintained in a lookup table that should be updated
as API pricing evolves.

Note: Image token costs are approximations. The actual cost may vary based
on image dimensions and provider-specific tokenization.
"""

from __future__ import annotations

from typing import TypedDict


class ModelPricing(TypedDict, total=False):
    """Pricing structure for a model.

    All prices are in USD per 1,000 tokens.
    """

    input: float
    output: float
    image_base: float  # OpenAI: base cost per image
    image_per_1k_px: float  # Anthropic: cost per 1000 pixels


# Pricing table: USD per 1,000 tokens
# Sources: OpenAI, Anthropic, Google pricing pages (as of Dec 2025)
# See docs/models/MODEL_REGISTRY.md for SSOT
PRICING_USD_PER_1K: dict[str, ModelPricing] = {
    # Claude Opus 4.5 - Best for coding & agents (80.9% SWE-bench)
    "claude-opus-4-5-20251101": {
        "input": 0.005,  # $5/1M tokens
        "output": 0.025,  # $25/1M tokens
        "image_per_1k_px": 0.00048,
    },
    # Gemini 3.0 Pro - 1M context, advanced reasoning
    "gemini-3-pro-preview": {
        "input": 0.002,  # $2/1M tokens
        "output": 0.012,  # $12/1M tokens
        # Gemini includes images in token count, no separate image cost
    },
    # GPT-5.2 - 400K context, cost-effective frontier model
    "gpt-5.2-2025-12-11": {
        "input": 0.00175,  # $1.75/1M tokens
        "output": 0.014,  # $14/1M tokens
        "image_base": 0.00255,
    },
}

# Default pricing for unknown models
_DEFAULT_PRICING: ModelPricing = {
    "input": 0.01,
    "output": 0.03,
}


def get_model_pricing(model: str) -> ModelPricing:
    """Get pricing for a model.

    Args:
        model: Model identifier (e.g., "gpt-5.2-2025-12-11").

    Returns:
        ModelPricing dictionary with input/output costs.
        Returns default pricing if model is not in the lookup table.
    """
    return PRICING_USD_PER_1K.get(model, _DEFAULT_PRICING)


def calculate_cost(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> float:
    """Calculate the cost of an API call in USD.

    This calculates the text token cost only. Image costs should be
    calculated separately using calculate_image_cost().

    Args:
        model: Model identifier.
        prompt_tokens: Number of input tokens.
        completion_tokens: Number of output tokens.

    Returns:
        Cost in USD.
    """
    pricing = get_model_pricing(model)
    input_cost = prompt_tokens * pricing.get("input", 0.01) / 1000
    output_cost = completion_tokens * pricing.get("output", 0.03) / 1000
    return input_cost + output_cost


def calculate_image_cost_openai(model: str, image_count: int = 1) -> float:
    """Calculate image cost for OpenAI models.

    OpenAI charges a base cost per image regardless of resolution
    (for the auto/low detail settings we use).

    Args:
        model: Model identifier.
        image_count: Number of images in the request.

    Returns:
        Image cost in USD.
    """
    pricing = get_model_pricing(model)
    base_cost = pricing.get("image_base", 0.00255)
    return base_cost * image_count


def calculate_image_cost_anthropic(
    model: str,
    image_pixels: int,
) -> float:
    """Calculate image cost for Anthropic models.

    Anthropic charges based on the number of pixels in the image.

    Args:
        model: Model identifier.
        image_pixels: Total number of pixels (width * height).

    Returns:
        Image cost in USD.
    """
    pricing = get_model_pricing(model)
    per_1k_px = pricing.get("image_per_1k_px", 0.00048)
    return (image_pixels / 1000) * per_1k_px


def calculate_total_cost(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    *,
    image_count: int = 0,
    image_pixels: int = 0,
    provider: str = "openai",
) -> float:
    """Calculate total cost including text and image tokens.

    Args:
        model: Model identifier.
        prompt_tokens: Number of input tokens.
        completion_tokens: Number of output tokens.
        image_count: Number of images (for OpenAI).
        image_pixels: Total pixels (for Anthropic).
        provider: Provider name ("openai" or "anthropic").

    Returns:
        Total cost in USD.
    """
    text_cost = calculate_cost(model, prompt_tokens, completion_tokens)

    if provider == "openai" and image_count > 0:
        return text_cost + calculate_image_cost_openai(model, image_count)
    elif provider == "anthropic" and image_pixels > 0:
        return text_cost + calculate_image_cost_anthropic(model, image_pixels)

    return text_cost
