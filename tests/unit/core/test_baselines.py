"""Tests for giant.core.baselines module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from giant.core.baselines import BaselineRequest, run_baseline_answer
from giant.llm.protocol import LLMParseError, TokenUsage


class TestRunBaselineAnswer:
    @pytest.mark.asyncio
    async def test_parse_error_tracks_usage_and_preserves_raw_output(self) -> None:
        provider = MagicMock()
        provider.generate_response = AsyncMock(
            side_effect=[
                LLMParseError(
                    "Failed to parse JSON",
                    raw_output="not json 1",
                    provider="mock",
                    usage=TokenUsage(
                        prompt_tokens=100,
                        completion_tokens=50,
                        total_tokens=150,
                        cost_usd=0.001,
                    ),
                ),
                LLMParseError(
                    "Failed to parse JSON",
                    raw_output="not json 2",
                    provider="mock",
                    usage=TokenUsage(
                        prompt_tokens=100,
                        completion_tokens=50,
                        total_tokens=150,
                        cost_usd=0.001,
                    ),
                ),
            ]
        )

        request = BaselineRequest(
            wsi_path=Path("/test/slide.svs"),
            question="What is the diagnosis?",
            image_base64="base64data...",
            media_type="image/jpeg",
            context_note="This is a test image.",
        )

        result = await run_baseline_answer(
            llm_provider=provider,
            request=request,
            max_attempts=2,
        )

        assert result.success is False
        assert result.answer == "not json 2"
        assert result.total_tokens == 300
        assert result.total_cost == pytest.approx(0.002)
