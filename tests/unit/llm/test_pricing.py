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

    def test_frontier_models_in_table(self) -> None:
        """Test that frontier models are in the pricing table."""
        assert "claude-opus-4-5-20251101" in PRICING_USD_PER_1K
        assert "gemini-3-pro-preview" in PRICING_USD_PER_1K
        assert "gpt-5.2" in PRICING_USD_PER_1K

    def test_only_frontier_models(self) -> None:
        """Test that only frontier models are in the pricing table."""
        assert len(PRICING_USD_PER_1K) == 3

    def test_pricing_has_required_keys(self) -> None:
        """Test that pricing entries have required keys."""
        for model, pricing in PRICING_USD_PER_1K.items():
            assert "input" in pricing, f"{model} missing 'input' pricing"
            assert "output" in pricing, f"{model} missing 'output' pricing"


class TestGetModelPricing:
    """Tests for get_model_pricing function."""

    def test_gpt52_pricing(self) -> None:
        """Test getting pricing for GPT-5.2."""
        pricing = get_model_pricing("gpt-5.2")
        assert pricing["input"] == 0.00175
        assert pricing["output"] == 0.014

    def test_claude_opus_pricing(self) -> None:
        """Test getting pricing for Claude Opus 4.5."""
        pricing = get_model_pricing("claude-opus-4-5-20251101")
        assert pricing["input"] == 0.005
        assert pricing["output"] == 0.025

    def test_gemini_pricing(self) -> None:
        """Test getting pricing for Gemini 3.0 Pro."""
        pricing = get_model_pricing("gemini-3-pro-preview")
        assert pricing["input"] == 0.002
        assert pricing["output"] == 0.012

    def test_unknown_model_raises(self) -> None:
        """Test that unknown models are rejected."""
        with pytest.raises(ValueError):
            get_model_pricing("")


class TestCalculateCost:
    """Tests for calculate_cost function."""

    def test_gpt52_cost(self) -> None:
        """Test cost calculation for GPT-5.2."""
        cost = calculate_cost("gpt-5.2", prompt_tokens=1000, completion_tokens=500)
        # 1000 * 0.00175/1000 + 500 * 0.014/1000 = 0.00175 + 0.007 = 0.00875
        assert cost == pytest.approx(0.00875)

    def test_claude_opus_cost(self) -> None:
        """Test cost calculation for Claude Opus 4.5."""
        cost = calculate_cost(
            "claude-opus-4-5-20251101", prompt_tokens=1000, completion_tokens=500
        )
        # 1000 * 0.005/1000 + 500 * 0.025/1000 = 0.005 + 0.0125 = 0.0175
        assert cost == pytest.approx(0.0175)

    def test_zero_tokens_zero_cost(self) -> None:
        """Test that zero tokens results in zero cost."""
        cost = calculate_cost("gpt-5.2", prompt_tokens=0, completion_tokens=0)
        assert cost == 0.0

    def test_unknown_model_raises(self) -> None:
        """Test that unknown models are rejected."""
        with pytest.raises(ValueError):
            calculate_cost("", prompt_tokens=1000, completion_tokens=500)


class TestCalculateImageCostOpenai:
    """Tests for calculate_image_cost_openai function."""

    def test_single_image(self) -> None:
        """Test cost for a single image."""
        cost = calculate_image_cost_openai("gpt-5.2", image_count=1)
        assert cost == pytest.approx(0.00255)

    def test_multiple_images(self) -> None:
        """Test cost for multiple images."""
        cost = calculate_image_cost_openai("gpt-5.2", image_count=3)
        assert cost == pytest.approx(0.00255 * 3)

    def test_zero_images(self) -> None:
        """Test zero images results in zero cost."""
        cost = calculate_image_cost_openai("gpt-5.2", image_count=0)
        assert cost == 0.0


class TestCalculateImageCostAnthropic:
    """Tests for calculate_image_cost_anthropic function."""

    def test_small_image(self) -> None:
        """Test cost for a small image (500x500)."""
        # 500 * 500 = 250,000 pixels
        cost = calculate_image_cost_anthropic(
            "claude-opus-4-5-20251101", image_pixels=250000
        )
        # 250000 / 1000 * 0.00048 = 250 * 0.00048 = 0.12
        assert cost == pytest.approx(0.12)

    def test_large_image(self) -> None:
        """Test cost for a large image (1000x1000)."""
        # 1000 * 1000 = 1,000,000 pixels
        cost = calculate_image_cost_anthropic(
            "claude-opus-4-5-20251101", image_pixels=1000000
        )
        # 1000000 / 1000 * 0.00048 = 1000 * 0.00048 = 0.48
        assert cost == pytest.approx(0.48)

    def test_zero_pixels(self) -> None:
        """Test zero pixels results in zero cost."""
        cost = calculate_image_cost_anthropic(
            "claude-opus-4-5-20251101", image_pixels=0
        )
        assert cost == 0.0


class TestCalculateTotalCost:
    """Tests for calculate_total_cost function."""

    def test_openai_text_only(self) -> None:
        """Test OpenAI total cost with text only."""
        cost = calculate_total_cost(
            "gpt-5.2",
            prompt_tokens=1000,
            completion_tokens=500,
            provider="openai",
        )
        assert cost == pytest.approx(0.00875)

    def test_openai_with_images(self) -> None:
        """Test OpenAI total cost with images."""
        cost = calculate_total_cost(
            "gpt-5.2",
            prompt_tokens=1000,
            completion_tokens=500,
            image_count=2,
            provider="openai",
        )
        # Text: 0.00875 + Images: 0.00255 * 2 = 0.00875 + 0.0051 = 0.01385
        assert cost == pytest.approx(0.01385)

    def test_anthropic_text_only(self) -> None:
        """Test Anthropic total cost with text only."""
        cost = calculate_total_cost(
            "claude-opus-4-5-20251101",
            prompt_tokens=1000,
            completion_tokens=500,
            provider="anthropic",
        )
        assert cost == pytest.approx(0.0175)

    def test_anthropic_with_images(self) -> None:
        """Test Anthropic total cost with images."""
        cost = calculate_total_cost(
            "claude-opus-4-5-20251101",
            prompt_tokens=1000,
            completion_tokens=500,
            image_pixels=250000,  # 500x500
            provider="anthropic",
        )
        # Text: 0.0175 + Images: 0.12 = 0.1375
        assert cost == pytest.approx(0.1375)
