"""Tests for giant.agent.runner module (Spec-09).

Tests the GIANTAgent core loop with mocked LLM and WSI components.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from giant.agent.runner import (
    ERROR_FEEDBACK_TEMPLATE,
    FORCE_ANSWER_TEMPLATE,
    AgentConfig,
    GIANTAgent,
    RunResult,
)
from giant.llm.protocol import (
    BoundingBoxAction,
    FinalAnswerAction,
    LLMError,
    LLMResponse,
    StepResponse,
    TokenUsage,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_wsi_reader() -> MagicMock:
    """Create a mock WSI reader."""
    reader = MagicMock()
    reader.__enter__ = MagicMock(return_value=reader)
    reader.__exit__ = MagicMock(return_value=None)

    # Create a small test image for thumbnail
    test_image = Image.new("RGB", (1024, 768), color="white")

    reader.get_thumbnail.return_value = test_image
    reader.get_metadata.return_value = MagicMock(
        width=100000,
        height=75000,
        level_count=5,
    )

    return reader


@pytest.fixture
def mock_crop_engine() -> MagicMock:
    """Create a mock crop engine."""
    engine = MagicMock()
    engine.crop.return_value = MagicMock(
        base64_content="cropped_image_base64",
        read_level=2,
        scale_factor=0.5,
    )
    return engine


@pytest.fixture
def mock_llm_provider() -> MagicMock:
    """Create a mock LLM provider."""
    provider = MagicMock()
    provider.get_model_name.return_value = "mock-model"
    provider.get_target_size.return_value = 1000
    provider.generate_response = AsyncMock()
    return provider


def make_crop_response(
    x: int,
    y: int,
    width: int,
    height: int,
    reasoning: str = "I see something interesting",
) -> LLMResponse:
    """Create a mock crop response."""
    return LLMResponse(
        step_response=StepResponse(
            reasoning=reasoning,
            action=BoundingBoxAction(x=x, y=y, width=width, height=height),
        ),
        usage=TokenUsage(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost_usd=0.001,
        ),
        model="mock-model",
        latency_ms=100.0,
    )


def make_answer_response(answer: str, reasoning: str = "Final analysis") -> LLMResponse:
    """Create a mock answer response."""
    return LLMResponse(
        step_response=StepResponse(
            reasoning=reasoning,
            action=FinalAnswerAction(answer_text=answer),
        ),
        usage=TokenUsage(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost_usd=0.001,
        ),
        model="mock-model",
        latency_ms=100.0,
    )


# =============================================================================
# Test Cases
# =============================================================================


class TestRunResult:
    """Tests for RunResult model."""

    def test_default_values(self) -> None:
        """Test RunResult default values."""
        from giant.agent.trajectory import Trajectory

        result = RunResult(
            trajectory=Trajectory(wsi_path="/test.svs", question="Test?")
        )
        assert result.answer == ""
        assert result.total_tokens == 0
        assert result.total_cost == 0.0
        assert result.success is False
        assert result.error_message is None

    def test_successful_result(self) -> None:
        """Test RunResult with success=True."""
        from giant.agent.trajectory import Trajectory

        result = RunResult(
            answer="Benign tissue",
            trajectory=Trajectory(wsi_path="/test.svs", question="Test?"),
            total_tokens=450,
            total_cost=0.003,
            success=True,
        )
        assert result.success is True
        assert result.answer == "Benign tissue"


class TestGIANTAgentHappyPath:
    """Tests for happy path scenarios."""

    @pytest.mark.asyncio
    async def test_crop_crop_answer(
        self,
        mock_wsi_reader: MagicMock,
        mock_crop_engine: MagicMock,
        mock_llm_provider: MagicMock,
    ) -> None:
        """Test happy path: Crop -> Crop -> Answer."""
        # Setup mock responses: 2 crops then answer
        mock_llm_provider.generate_response.side_effect = [
            make_crop_response(1000, 2000, 500, 500, "Found region A"),
            make_crop_response(1500, 2500, 300, 300, "Zooming into region A"),
            make_answer_response("Benign tissue", "Based on analysis"),
        ]

        with patch("giant.agent.runner.WSIReader", return_value=mock_wsi_reader):
            with patch("giant.agent.runner.CropEngine", return_value=mock_crop_engine):
                agent = GIANTAgent(
                    wsi_path="/test/slide.svs",
                    question="Is this malignant?",
                    llm_provider=mock_llm_provider,
                    config=AgentConfig(max_steps=5),
                )

                result = await agent.run()

        assert result.success is True
        assert result.answer == "Benign tissue"
        assert result.total_tokens == 450  # 3 calls * 150 tokens
        assert result.total_cost == pytest.approx(0.003)
        assert len(result.trajectory.turns) == 3

    @pytest.mark.asyncio
    async def test_early_answer(
        self,
        mock_wsi_reader: MagicMock,
        mock_crop_engine: MagicMock,
        mock_llm_provider: MagicMock,
    ) -> None:
        """Test early termination with answer on first step."""
        mock_llm_provider.generate_response.side_effect = [
            make_answer_response("Obviously benign", "Clear from thumbnail"),
        ]

        with patch("giant.agent.runner.WSIReader", return_value=mock_wsi_reader):
            with patch("giant.agent.runner.CropEngine", return_value=mock_crop_engine):
                agent = GIANTAgent(
                    wsi_path="/test/slide.svs",
                    question="Is this malignant?",
                    llm_provider=mock_llm_provider,
                )

                result = await agent.run()

        assert result.success is True
        assert result.answer == "Obviously benign"
        assert len(result.trajectory.turns) == 1


class TestGIANTAgentLoopLimit:
    """Tests for max steps and force answer."""

    @pytest.mark.asyncio
    async def test_force_answer_at_max_steps(
        self,
        mock_wsi_reader: MagicMock,
        mock_crop_engine: MagicMock,
        mock_llm_provider: MagicMock,
    ) -> None:
        """Test that agent forces answer at max_steps."""
        # Always return crop except when forced
        crop_responses = [
            make_crop_response(i * 100, i * 100, 500, 500) for i in range(10)
        ]
        # After force prompt, return answer
        answer_response = make_answer_response("Forced answer", "Had to decide")

        mock_llm_provider.generate_response.side_effect = [
            *crop_responses[:2],  # 2 crops (step 1, 2)
            answer_response,  # Force answer at step 3 (max_steps)
        ]

        with patch("giant.agent.runner.WSIReader", return_value=mock_wsi_reader):
            with patch("giant.agent.runner.CropEngine", return_value=mock_crop_engine):
                agent = GIANTAgent(
                    wsi_path="/test/slide.svs",
                    question="Is this malignant?",
                    llm_provider=mock_llm_provider,
                    config=AgentConfig(max_steps=3),
                )

                result = await agent.run()

        assert result.success is True
        assert result.answer == "Forced answer"

    @pytest.mark.asyncio
    async def test_force_answer_retries_exceeded(
        self,
        mock_wsi_reader: MagicMock,
        mock_crop_engine: MagicMock,
        mock_llm_provider: MagicMock,
    ) -> None:
        """Test failure when model keeps cropping at force answer."""
        # Always return crop, even after force prompt
        mock_llm_provider.generate_response.side_effect = [
            make_crop_response(i * 100, i * 100, 500, 500)
            for i in range(20)  # More than enough
        ]

        with patch("giant.agent.runner.WSIReader", return_value=mock_wsi_reader):
            with patch("giant.agent.runner.CropEngine", return_value=mock_crop_engine):
                agent = GIANTAgent(
                    wsi_path="/test/slide.svs",
                    question="Is this malignant?",
                    llm_provider=mock_llm_provider,
                    config=AgentConfig(max_steps=2, force_answer_retries=3),
                )

                result = await agent.run()

        assert result.success is False
        assert "retries" in result.error_message.lower()


class TestGIANTAgentErrorRecovery:
    """Tests for error handling and recovery."""

    @pytest.mark.asyncio
    async def test_invalid_coordinates_then_valid(
        self,
        mock_wsi_reader: MagicMock,
        mock_crop_engine: MagicMock,
        mock_llm_provider: MagicMock,
    ) -> None:
        """Test recovery from invalid coordinates."""
        # First response has coordinates outside bounds (slide is 100000x75000)
        invalid_crop = make_crop_response(99000, 74000, 5000, 5000)
        # After error feedback, valid coordinates
        valid_crop = make_crop_response(1000, 1000, 500, 500)
        answer = make_answer_response("Recovered", "After retry")

        mock_llm_provider.generate_response.side_effect = [
            invalid_crop,  # Invalid
            valid_crop,  # Valid after error feedback
            answer,  # Final answer
        ]

        with patch("giant.agent.runner.WSIReader", return_value=mock_wsi_reader):
            with patch("giant.agent.runner.CropEngine", return_value=mock_crop_engine):
                agent = GIANTAgent(
                    wsi_path="/test/slide.svs",
                    question="Is this malignant?",
                    llm_provider=mock_llm_provider,
                    config=AgentConfig(max_steps=5, max_retries=3),
                )

                result = await agent.run()

        assert result.success is True
        assert result.answer == "Recovered"

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(
        self,
        mock_wsi_reader: MagicMock,
        mock_crop_engine: MagicMock,
        mock_llm_provider: MagicMock,
    ) -> None:
        """Test termination after max retries on invalid coordinates."""
        # Always return invalid coordinates (outside 100000x75000 bounds)
        mock_llm_provider.generate_response.side_effect = [
            make_crop_response(99000, 74000, 5000, 5000) for _ in range(10)
        ]

        with patch("giant.agent.runner.WSIReader", return_value=mock_wsi_reader):
            with patch("giant.agent.runner.CropEngine", return_value=mock_crop_engine):
                agent = GIANTAgent(
                    wsi_path="/test/slide.svs",
                    question="Is this malignant?",
                    llm_provider=mock_llm_provider,
                    config=AgentConfig(max_steps=5, max_retries=3),
                )

                result = await agent.run()

        assert result.success is False
        assert "max retries" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_llm_error_recovery(
        self,
        mock_wsi_reader: MagicMock,
        mock_crop_engine: MagicMock,
        mock_llm_provider: MagicMock,
    ) -> None:
        """Test recovery from LLM API errors."""
        mock_llm_provider.generate_response.side_effect = [
            LLMError("API error", provider="mock"),  # Error
            make_answer_response("Recovered", "After error"),  # Success
        ]

        with patch("giant.agent.runner.WSIReader", return_value=mock_wsi_reader):
            with patch("giant.agent.runner.CropEngine", return_value=mock_crop_engine):
                agent = GIANTAgent(
                    wsi_path="/test/slide.svs",
                    question="Is this malignant?",
                    llm_provider=mock_llm_provider,
                    config=AgentConfig(max_steps=5, max_retries=3),
                )

                result = await agent.run()

        assert result.success is True
        assert result.answer == "Recovered"


class TestGIANTAgentBudget:
    """Tests for budget constraints."""

    @pytest.mark.asyncio
    async def test_budget_exceeded(
        self,
        mock_wsi_reader: MagicMock,
        mock_crop_engine: MagicMock,
        mock_llm_provider: MagicMock,
    ) -> None:
        """Test budget exceeded triggers force answer."""
        # First call succeeds, second is after budget check
        mock_llm_provider.generate_response.side_effect = [
            make_crop_response(1000, 2000, 500, 500),  # Cost: 0.001
            make_answer_response("Budget answer", "Forced by budget"),
        ]

        with patch("giant.agent.runner.WSIReader", return_value=mock_wsi_reader):
            with patch("giant.agent.runner.CropEngine", return_value=mock_crop_engine):
                agent = GIANTAgent(
                    wsi_path="/test/slide.svs",
                    question="Is this malignant?",
                    llm_provider=mock_llm_provider,
                    config=AgentConfig(max_steps=10, budget_usd=0.001),
                )

                result = await agent.run()

        # Budget exceeded, but still got an answer
        assert result.success is False
        assert result.error_message == "Budget exceeded"
        assert result.answer == "Budget answer"


class TestTemplates:
    """Tests for error and force answer templates."""

    def test_error_feedback_template_format(self) -> None:
        """Test error feedback template formats correctly."""
        formatted = ERROR_FEEDBACK_TEMPLATE.format(
            x=99000,
            y=74000,
            width=5000,
            height=5000,
            max_width=100000,
            max_height=75000,
            issues="right edge exceeds width",
        )

        assert "99000" in formatted
        assert "74000" in formatted
        assert "100000" in formatted
        assert "75000" in formatted
        assert "right edge exceeds width" in formatted

    def test_force_answer_template_format(self) -> None:
        """Test force answer template formats correctly."""
        formatted = FORCE_ANSWER_TEMPLATE.format(
            max_steps=5,
            observation_summary="- Step 1: Found tissue\n- Step 2: Zoomed in",
            question="Is this malignant?",
        )

        assert "5" in formatted
        assert "Found tissue" in formatted
        assert "Zoomed in" in formatted
        assert "Is this malignant?" in formatted


class TestObservationSummary:
    """Tests for observation summary generation."""

    @pytest.mark.asyncio
    async def test_observation_summary_in_force_answer(
        self,
        mock_wsi_reader: MagicMock,
        mock_crop_engine: MagicMock,
        mock_llm_provider: MagicMock,
    ) -> None:
        """Test that force answer includes observation summary."""
        captured_messages: list = []

        async def capture_messages(messages):
            captured_messages.append(messages)
            # Return answer on force prompt (contains "MUST now provide")
            for msg in messages:
                for content in msg.content:
                    if content.text and "MUST now provide" in content.text:
                        return make_answer_response("Final", "Forced")
            # Otherwise return crop
            return make_crop_response(1000, 2000, 500, 500, "Step reasoning")

        mock_llm_provider.generate_response.side_effect = capture_messages

        with patch("giant.agent.runner.WSIReader", return_value=mock_wsi_reader):
            with patch("giant.agent.runner.CropEngine", return_value=mock_crop_engine):
                agent = GIANTAgent(
                    wsi_path="/test/slide.svs",
                    question="Is this malignant?",
                    llm_provider=mock_llm_provider,
                    config=AgentConfig(max_steps=2),
                )

                result = await agent.run()

        assert result.success is True

        # Check that force answer message contained observation summary
        force_messages = captured_messages[-1]
        force_text = ""
        for msg in force_messages:
            for content in msg.content:
                if content.text and "MUST now provide" in content.text:
                    force_text = content.text
                    break

        assert "Step reasoning" in force_text or "Step 1" in force_text
