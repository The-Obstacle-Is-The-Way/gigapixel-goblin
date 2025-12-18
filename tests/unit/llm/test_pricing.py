"""Tests for giant.llm.pricing module."""

import pytest

from giant.llm.pricing import (
    PRICING_USD_PER_1K,
    calculate_cost,
    calculate_image_cost_anthropic,
    calculate_image_cost_openai,
    calculate_total_cost,
    get_model_pricing,
)


class TestPricingTable:
    """Tests for the pricing lookup table."""

    def test_known_models_in_table(self) -> None:
        """Test that known models are in the pricing table."""
        assert "gpt-4o" in PRICING_USD_PER_1K
        assert "gpt-5" in PRICING_USD_PER_1K
        assert "claude-4-5-sonnet" in PRICING_USD_PER_1K

    def test_pricing_has_required_keys(self) -> None:
        """Test that pricing entries have required keys."""
        for model, pricing in PRICING_USD_PER_1K.items():
            assert "input" in pricing, f"{model} missing 'input' pricing"
            assert "output" in pricing, f"{model} missing 'output' pricing"


class TestGetModelPricing:
    """Tests for get_model_pricing function."""

    def test_known_model(self) -> None:
        """Test getting pricing for a known model."""
        pricing = get_model_pricing("gpt-4o")
        assert pricing["input"] == 0.005
        assert pricing["output"] == 0.015

    def test_unknown_model_returns_default(self) -> None:
        """Test that unknown models get default pricing."""
        pricing = get_model_pricing("unknown-model-xyz")
        assert pricing["input"] == 0.01
        assert pricing["output"] == 0.03


class TestCalculateCost:
    """Tests for calculate_cost function."""

    def test_gpt4o_cost(self) -> None:
        """Test cost calculation for GPT-4o."""
        cost = calculate_cost("gpt-4o", prompt_tokens=1000, completion_tokens=500)
        # 1000 * 0.005/1000 + 500 * 0.015/1000 = 0.005 + 0.0075 = 0.0125
        assert cost == pytest.approx(0.0125)

    def test_claude_cost(self) -> None:
        """Test cost calculation for Claude."""
        cost = calculate_cost(
            "claude-4-5-sonnet", prompt_tokens=1000, completion_tokens=500
        )
        # 1000 * 0.003/1000 + 500 * 0.015/1000 = 0.003 + 0.0075 = 0.0105
        assert cost == pytest.approx(0.0105)

    def test_zero_tokens_zero_cost(self) -> None:
        """Test that zero tokens results in zero cost."""
        cost = calculate_cost("gpt-4o", prompt_tokens=0, completion_tokens=0)
        assert cost == 0.0

    def test_unknown_model_uses_default(self) -> None:
        """Test that unknown models use default pricing."""
        cost = calculate_cost(
            "unknown-model", prompt_tokens=1000, completion_tokens=500
        )
        # 1000 * 0.01/1000 + 500 * 0.03/1000 = 0.01 + 0.015 = 0.025
        assert cost == pytest.approx(0.025)


class TestCalculateImageCostOpenai:
    """Tests for calculate_image_cost_openai function."""

    def test_single_image(self) -> None:
        """Test cost for a single image."""
        cost = calculate_image_cost_openai("gpt-4o", image_count=1)
        assert cost == pytest.approx(0.00255)

    def test_multiple_images(self) -> None:
        """Test cost for multiple images."""
        cost = calculate_image_cost_openai("gpt-4o", image_count=3)
        assert cost == pytest.approx(0.00255 * 3)

    def test_zero_images(self) -> None:
        """Test zero images results in zero cost."""
        cost = calculate_image_cost_openai("gpt-4o", image_count=0)
        assert cost == 0.0


class TestCalculateImageCostAnthropic:
    """Tests for calculate_image_cost_anthropic function."""

    def test_small_image(self) -> None:
        """Test cost for a small image (500x500)."""
        # 500 * 500 = 250,000 pixels
        cost = calculate_image_cost_anthropic("claude-4-5-sonnet", image_pixels=250000)
        # 250000 / 1000 * 0.00048 = 250 * 0.00048 = 0.12
        assert cost == pytest.approx(0.12)

    def test_large_image(self) -> None:
        """Test cost for a large image (1000x1000)."""
        # 1000 * 1000 = 1,000,000 pixels
        cost = calculate_image_cost_anthropic("claude-4-5-sonnet", image_pixels=1000000)
        # 1000000 / 1000 * 0.00048 = 1000 * 0.00048 = 0.48
        assert cost == pytest.approx(0.48)

    def test_zero_pixels(self) -> None:
        """Test zero pixels results in zero cost."""
        cost = calculate_image_cost_anthropic("claude-4-5-sonnet", image_pixels=0)
        assert cost == 0.0


class TestCalculateTotalCost:
    """Tests for calculate_total_cost function."""

    def test_openai_text_only(self) -> None:
        """Test OpenAI total cost with text only."""
        cost = calculate_total_cost(
            "gpt-4o",
            prompt_tokens=1000,
            completion_tokens=500,
            provider="openai",
        )
        assert cost == pytest.approx(0.0125)

    def test_openai_with_images(self) -> None:
        """Test OpenAI total cost with images."""
        cost = calculate_total_cost(
            "gpt-4o",
            prompt_tokens=1000,
            completion_tokens=500,
            image_count=2,
            provider="openai",
        )
        # Text: 0.0125 + Images: 0.00255 * 2 = 0.0125 + 0.0051 = 0.0176
        assert cost == pytest.approx(0.0176)

    def test_anthropic_text_only(self) -> None:
        """Test Anthropic total cost with text only."""
        cost = calculate_total_cost(
            "claude-4-5-sonnet",
            prompt_tokens=1000,
            completion_tokens=500,
            provider="anthropic",
        )
        assert cost == pytest.approx(0.0105)

    def test_anthropic_with_images(self) -> None:
        """Test Anthropic total cost with images."""
        cost = calculate_total_cost(
            "claude-4-5-sonnet",
            prompt_tokens=1000,
            completion_tokens=500,
            image_pixels=250000,  # 500x500
            provider="anthropic",
        )
        # Text: 0.0105 + Images: 0.12 = 0.1305
        assert cost == pytest.approx(0.1305)
