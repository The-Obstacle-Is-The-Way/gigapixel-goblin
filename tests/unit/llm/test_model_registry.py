"""Tests for giant.llm.model_registry module."""

import pytest

from giant.llm.model_registry import (
    ANTHROPIC_MODELS,
    APPROVED_MODELS,
    APPROVED_MODELS_BY_PROVIDER,
    GOOGLE_MODELS,
    OPENAI_MODELS,
    validate_model_id,
)


class TestModelConstants:
    """Tests for model registry constants."""

    def test_approved_models_count(self) -> None:
        """Test that exactly 3 frontier models are approved."""
        assert len(APPROVED_MODELS) == 3

    def test_openai_models(self) -> None:
        """Test OpenAI approved models."""
        assert OPENAI_MODELS == frozenset({"gpt-5.2"})

    def test_anthropic_models(self) -> None:
        """Test Anthropic approved models."""
        assert ANTHROPIC_MODELS == frozenset({"claude-opus-4-5-20251101"})

    def test_google_models(self) -> None:
        """Test Google approved models."""
        assert GOOGLE_MODELS == frozenset({"gemini-3-pro-preview"})

    def test_approved_models_is_union(self) -> None:
        """Test APPROVED_MODELS is the union of all provider models."""
        expected = OPENAI_MODELS | ANTHROPIC_MODELS | GOOGLE_MODELS
        assert APPROVED_MODELS == expected

    def test_approved_models_by_provider(self) -> None:
        """Test provider-to-models mapping."""
        assert APPROVED_MODELS_BY_PROVIDER["openai"] == OPENAI_MODELS
        assert APPROVED_MODELS_BY_PROVIDER["anthropic"] == ANTHROPIC_MODELS
        assert APPROVED_MODELS_BY_PROVIDER["google"] == GOOGLE_MODELS

    def test_no_legacy_models(self) -> None:
        """Test legacy models are not in approved list."""
        legacy_models = [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-5",
            "gpt-5.2-pro-2025-12-11",
            "claude-3-opus-20240229",
            "claude-3-5-sonnet-20241022",
            "claude-4-5-sonnet",
            "gemini-1.5-pro",
            "gemini-2.0-flash",
        ]
        for model in legacy_models:
            assert model not in APPROVED_MODELS, f"{model} should not be approved"


class TestValidateModelId:
    """Tests for validate_model_id function."""

    def test_validate_gpt52(self) -> None:
        """Test GPT-5.2 is valid."""
        validate_model_id("gpt-5.2")  # Should not raise

    def test_validate_claude_opus(self) -> None:
        """Test Claude Opus 4.5 is valid."""
        validate_model_id("claude-opus-4-5-20251101")  # Should not raise

    def test_validate_gemini(self) -> None:
        """Test Gemini 3.0 Pro is valid."""
        validate_model_id("gemini-3-pro-preview")  # Should not raise

    def test_reject_unknown_model(self) -> None:
        """Test unknown models are rejected."""
        with pytest.raises(ValueError) as exc_info:
            validate_model_id("unknown-model-xyz")
        assert "not approved" in str(exc_info.value)
        assert "MODEL_REGISTRY.md" in str(exc_info.value)

    def test_reject_legacy_gpt4o(self) -> None:
        """Test gpt-4o is rejected."""
        with pytest.raises(ValueError) as exc_info:
            validate_model_id("gpt-4o")
        assert "not approved" in str(exc_info.value)

    def test_reject_legacy_claude3(self) -> None:
        """Test claude-3 models are rejected."""
        with pytest.raises(ValueError) as exc_info:
            validate_model_id("claude-3-opus-20240229")
        assert "not approved" in str(exc_info.value)

    def test_reject_empty_model(self) -> None:
        """Test empty string is rejected."""
        with pytest.raises(ValueError):
            validate_model_id("")


class TestValidateModelIdWithProvider:
    """Tests for validate_model_id with provider constraint."""

    def test_gpt52_valid_for_openai(self) -> None:
        """Test GPT-5.2 is valid for OpenAI provider."""
        validate_model_id("gpt-5.2", provider="openai")

    def test_claude_valid_for_anthropic(self) -> None:
        """Test Claude is valid for Anthropic provider."""
        validate_model_id("claude-opus-4-5-20251101", provider="anthropic")

    def test_gemini_valid_for_google(self) -> None:
        """Test Gemini is valid for Google provider."""
        validate_model_id("gemini-3-pro-preview", provider="google")

    def test_reject_claude_for_openai(self) -> None:
        """Test Claude model rejected for OpenAI provider."""
        with pytest.raises(ValueError) as exc_info:
            validate_model_id("claude-opus-4-5-20251101", provider="openai")
        assert "not approved" in str(exc_info.value)
        assert "openai" in str(exc_info.value)

    def test_reject_gpt_for_anthropic(self) -> None:
        """Test GPT model rejected for Anthropic provider."""
        with pytest.raises(ValueError) as exc_info:
            validate_model_id("gpt-5.2", provider="anthropic")
        assert "not approved" in str(exc_info.value)
        assert "anthropic" in str(exc_info.value)

    def test_reject_unknown_provider(self) -> None:
        """Test unknown provider is rejected."""
        with pytest.raises(ValueError) as exc_info:
            validate_model_id("gpt-5.2", provider="unknown")
        assert "Unknown provider" in str(exc_info.value)
        assert "Supported providers" in str(exc_info.value)
