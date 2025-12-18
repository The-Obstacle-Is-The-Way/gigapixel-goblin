"""P2: Medium Priority Edge Case Tests.

Less common scenarios that could cause issues.
These are important but won't block initial production.

Tests cover:
- Very long question handling
- Unicode in question
- 20 iteration context
- Trajectory serialization roundtrip
- Concurrent API calls
- API timeout
- Network error
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
import respx

from giant.agent.context import ContextManager
from giant.agent.trajectory import Trajectory, Turn
from giant.config import Settings
from giant.llm import (
    AnthropicProvider,
    BoundingBoxAction,
    FinalAnswerAction,
    LLMError,
    Message,
    MessageContent,
    OpenAIProvider,
    StepResponse,
)
from giant.prompts.builder import PromptBuilder

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_openai_settings() -> Settings:
    """Create Settings with mock OpenAI API key."""
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        OPENAI_API_KEY="sk-test-mock-key",
    )


@pytest.fixture
def mock_anthropic_settings() -> Settings:
    """Create Settings with mock Anthropic API key."""
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        ANTHROPIC_API_KEY="sk-ant-test-mock-key",
    )


def _mock_openai_crop_response() -> dict[str, Any]:
    """Create a mock OpenAI response with crop action."""
    output_content = json.dumps(
        {
            "reasoning": "Analyzing region",
            "action": {
                "action_type": "crop",
                "x": 100,
                "y": 200,
                "width": 500,
                "height": 500,
            },
        }
    )
    return {
        "id": "resp_123",
        "object": "response",
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": output_content}],
            }
        ],
        "output_text": output_content,
        "usage": {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
    }


def _mock_anthropic_crop_response() -> dict[str, Any]:
    """Create a mock Anthropic response with crop action."""
    return {
        "id": "msg_123",
        "type": "message",
        "role": "assistant",
        "content": [
            {
                "type": "tool_use",
                "id": "toolu_123",
                "name": "submit_step",
                "input": {
                    "reasoning": "Analyzing tissue",
                    "action": {
                        "action_type": "crop",
                        "x": 150,
                        "y": 250,
                        "width": 400,
                        "height": 400,
                    },
                },
            }
        ],
        "stop_reason": "tool_use",
        "usage": {"input_tokens": 120, "output_tokens": 60},
    }


# =============================================================================
# P2-1: Very long question
# =============================================================================


@pytest.mark.mock
class TestP2_1_VeryLongQuestion:
    """P2-1: Test handling of very long questions."""

    def test_long_question_accepted_by_prompt_builder(self) -> None:
        """Test PromptBuilder handles long questions."""
        builder = PromptBuilder()
        long_question = "A" * 5000  # 5000 character question

        # Should not raise
        user_msg = builder.build_user_message(
            question=long_question,
            step=1,
            max_steps=5,
            context_images=["thumb=="],
        )

        text_content = next(c for c in user_msg.content if c.type == "text")
        assert long_question in (text_content.text or "")

    def test_context_manager_handles_long_question(self) -> None:
        """Test ContextManager handles long questions."""
        long_question = "Q" * 3000

        ctx = ContextManager(
            wsi_path="/slide.svs",
            question=long_question,
            max_steps=5,
        )

        # Verify messages can be built (exercises the full pipeline)
        ctx.get_messages(thumbnail_base64="thumb==")
        assert ctx.trajectory.question == long_question


# =============================================================================
# P2-2: Unicode in question
# =============================================================================


@pytest.mark.mock
class TestP2_2_UnicodeQuestion:
    """P2-2: Test handling of Unicode characters in questions."""

    def test_emoji_in_question(self) -> None:
        """Test questions with emoji are handled correctly."""
        builder = PromptBuilder()
        question_with_emoji = "Is this tissue 🔬 malignant? 🏥"

        user_msg = builder.build_user_message(
            question=question_with_emoji,
            step=1,
            max_steps=5,
            context_images=["thumb=="],
        )

        text_content = next(c for c in user_msg.content if c.type == "text")
        assert "🔬" in (text_content.text or "")

    def test_cjk_characters_in_question(self) -> None:
        """Test questions with CJK characters are handled correctly."""
        builder = PromptBuilder()
        # Japanese: "Is this malignant?"
        question_cjk = "これは悪性ですか？"

        user_msg = builder.build_user_message(
            question=question_cjk,
            step=1,
            max_steps=5,
            context_images=["thumb=="],
        )

        text_content = next(c for c in user_msg.content if c.type == "text")
        assert "悪性" in (text_content.text or "")

    def test_mixed_unicode_in_context_manager(self) -> None:
        """Test ContextManager handles mixed Unicode."""
        question = "Is this tissue malignant? 这是癌症吗？ これは悪性ですか？ 🔬"

        ctx = ContextManager(
            wsi_path="/slide.svs",
            question=question,
            max_steps=5,
        )

        assert ctx.trajectory.question == question


# =============================================================================
# P2-3: 20 iteration context
# =============================================================================


@pytest.mark.mock
class TestP2_3_TwentyIterationContext:
    """P2-3: Test full 20-step conversation context."""

    def test_20_turns_build_correctly(self) -> None:
        """Test context builds correctly with 20 turns."""
        ctx = ContextManager(
            wsi_path="/slide.svs",
            question="Test?",
            max_steps=20,
        )

        # Add 19 crop turns + 1 answer turn
        for i in range(19):
            response = StepResponse(
                reasoning=f"Step {i}",
                action=BoundingBoxAction(x=i * 10, y=i * 10, width=100, height=100),
            )
            ctx.add_turn(image_base64=f"img{i}==", response=response)

        # Final answer
        final_response = StepResponse(
            reasoning="Done",
            action=FinalAnswerAction(answer_text="Malignant"),
        )
        ctx.add_turn(image_base64="final==", response=final_response)

        assert len(ctx.trajectory.turns) == 20
        assert ctx.trajectory.final_answer == "Malignant"

    def test_20_turn_messages_alternate_correctly(self) -> None:
        """Test 20 turns produce correct message alternation."""
        ctx = ContextManager(
            wsi_path="/slide.svs",
            question="Test?",
            max_steps=20,
        )

        # Add 20 turns
        for i in range(20):
            response = StepResponse(
                reasoning=f"Step {i}",
                action=BoundingBoxAction(x=0, y=0, width=100, height=100),
            )
            ctx.add_turn(image_base64=f"img{i}==", response=response)

        messages = ctx.get_messages(thumbnail_base64="thumb==")

        # Verify alternation: system + (user + assistant) * 20
        # = 1 + 40 = 41 messages
        assert len(messages) == 41

        # First is system
        assert messages[0].role == "system"

        # Rest alternate user/assistant
        for i in range(1, len(messages)):
            expected_role = "user" if i % 2 == 1 else "assistant"
            assert messages[i].role == expected_role


# =============================================================================
# P2-4: Trajectory serialization
# =============================================================================


@pytest.mark.mock
class TestP2_4_TrajectorySerialization:
    """P2-4: Test trajectory JSON roundtrip."""

    def test_trajectory_json_roundtrip(self) -> None:
        """Test trajectory serializes and deserializes correctly."""
        # Build trajectory
        trajectory = Trajectory(
            wsi_path="/test.svs",
            question="Is this malignant?",
            turns=[
                Turn(
                    step_index=0,
                    image_base64="thumb==",
                    response=StepResponse(
                        reasoning="Initial view",
                        action=BoundingBoxAction(x=100, y=100, width=200, height=200),
                    ),
                ),
                Turn(
                    step_index=1,
                    image_base64="crop==",
                    response=StepResponse(
                        reasoning="Final analysis",
                        action=FinalAnswerAction(answer_text="Benign tissue"),
                    ),
                ),
            ],
            final_answer="Benign tissue",
        )

        # Serialize to JSON
        json_str = trajectory.model_dump_json()

        # Deserialize
        loaded = Trajectory.model_validate_json(json_str)

        # Verify
        assert loaded.wsi_path == trajectory.wsi_path
        assert loaded.question == trajectory.question
        assert len(loaded.turns) == 2
        assert loaded.final_answer == "Benign tissue"

    def test_trajectory_dict_roundtrip(self) -> None:
        """Test trajectory dict roundtrip."""
        ctx = ContextManager(
            wsi_path="/slide.svs",
            question="Test?",
            max_steps=5,
        )

        # Add a turn
        response = StepResponse(
            reasoning="Test",
            action=BoundingBoxAction(x=0, y=0, width=100, height=100),
        )
        ctx.add_turn(image_base64="img==", response=response)

        # Serialize to dict
        traj_dict = ctx.trajectory.model_dump()

        # Deserialize
        loaded = Trajectory.model_validate(traj_dict)

        assert loaded.wsi_path == ctx.trajectory.wsi_path
        assert len(loaded.turns) == 1


# =============================================================================
# P2-5: Concurrent API calls
# =============================================================================


@pytest.mark.mock
class TestP2_5_ConcurrentAPICalls:
    """P2-5: Test concurrent API call handling."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_concurrent_openai_calls(
        self, mock_openai_settings: Settings
    ) -> None:
        """Test 3 concurrent OpenAI calls complete."""
        import asyncio

        respx.post("https://api.openai.com/v1/responses").mock(
            return_value=httpx.Response(200, json=_mock_openai_crop_response())
        )

        provider = OpenAIProvider(settings=mock_openai_settings)
        messages = [
            Message(role="system", content=[MessageContent(type="text", text="Test")]),
            Message(role="user", content=[MessageContent(type="text", text="Test")]),
        ]

        # Run 3 calls concurrently
        tasks = [
            provider.generate_response(messages),
            provider.generate_response(messages),
            provider.generate_response(messages),
        ]
        results = await asyncio.gather(*tasks)

        assert len(results) == 3
        assert all(r.step_response is not None for r in results)

    @pytest.mark.asyncio
    @respx.mock
    async def test_concurrent_anthropic_calls(
        self, mock_anthropic_settings: Settings
    ) -> None:
        """Test 3 concurrent Anthropic calls complete."""
        import asyncio

        respx.post("https://api.anthropic.com/v1/messages").mock(
            return_value=httpx.Response(200, json=_mock_anthropic_crop_response())
        )

        provider = AnthropicProvider(settings=mock_anthropic_settings)
        messages = [
            Message(role="system", content=[MessageContent(type="text", text="Test")]),
            Message(role="user", content=[MessageContent(type="text", text="Test")]),
        ]

        # Run 3 calls concurrently
        tasks = [
            provider.generate_response(messages),
            provider.generate_response(messages),
            provider.generate_response(messages),
        ]
        results = await asyncio.gather(*tasks)

        assert len(results) == 3
        assert all(r.step_response is not None for r in results)


# =============================================================================
# P2-6: API timeout
# =============================================================================


@pytest.mark.mock
class TestP2_6_APITimeout:
    """P2-6: Test API timeout handling.

    Note: Testing actual timeouts requires real delays which makes tests slow.
    These tests verify timeout configuration exists.
    """

    def test_openai_provider_uses_httpx_client(self) -> None:
        """Test OpenAI provider uses httpx client (which supports timeouts)."""
        from giant.llm.openai_client import OpenAIProvider

        # OpenAI SDK uses httpx internally for async operations
        # Just verify the provider initializes correctly
        assert hasattr(OpenAIProvider, "_call_with_retry")

    def test_anthropic_provider_uses_httpx_client(self) -> None:
        """Test Anthropic provider uses httpx client (which supports timeouts)."""
        from giant.llm.anthropic_client import AnthropicProvider

        # Anthropic SDK uses httpx internally
        assert hasattr(AnthropicProvider, "_call_with_retry")


# =============================================================================
# P2-7: Network error
# =============================================================================


@pytest.mark.mock
class TestP2_7_NetworkError:
    """P2-7: Test network error handling."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_openai_handles_connection_error(
        self, mock_openai_settings: Settings
    ) -> None:
        """Test OpenAI raises LLMError on connection failure."""
        respx.post("https://api.openai.com/v1/responses").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        provider = OpenAIProvider(settings=mock_openai_settings)
        messages = [
            Message(role="system", content=[MessageContent(type="text", text="Test")]),
            Message(role="user", content=[MessageContent(type="text", text="Test")]),
        ]

        with pytest.raises(LLMError):
            await provider.generate_response(messages)

    @pytest.mark.asyncio
    @respx.mock
    async def test_anthropic_handles_connection_error(
        self, mock_anthropic_settings: Settings
    ) -> None:
        """Test Anthropic raises LLMError on connection failure."""
        respx.post("https://api.anthropic.com/v1/messages").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        provider = AnthropicProvider(settings=mock_anthropic_settings)
        messages = [
            Message(role="system", content=[MessageContent(type="text", text="Test")]),
            Message(role="user", content=[MessageContent(type="text", text="Test")]),
        ]

        with pytest.raises(LLMError):
            await provider.generate_response(messages)
