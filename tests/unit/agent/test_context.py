"""Tests for giant.agent.context module.

TDD tests for ContextManager following Spec-08.
"""

from giant.agent.context import ContextManager
from giant.geometry.primitives import Region
from giant.llm.protocol import (
    BoundingBoxAction,
    ConchAction,
    FinalAnswerAction,
    StepResponse,
)


class TestContextManagerInit:
    """Tests for ContextManager initialization."""

    def test_init_creates_empty_trajectory(self) -> None:
        """Test that initialization creates empty trajectory."""
        ctx = ContextManager(
            wsi_path="/slide.svs",
            question="What is this?",
            max_steps=5,
        )
        assert ctx.trajectory.wsi_path == "/slide.svs"
        assert ctx.trajectory.question == "What is this?"
        assert len(ctx.trajectory.turns) == 0

    def test_init_with_default_max_history_images(self) -> None:
        """Test that max_history_images defaults to None (keep all)."""
        ctx = ContextManager(
            wsi_path="/slide.svs",
            question="Q?",
            max_steps=5,
        )
        assert ctx.max_history_images is None

    def test_init_with_custom_max_history_images(self) -> None:
        """Test initialization with custom image limit."""
        ctx = ContextManager(
            wsi_path="/slide.svs",
            question="Q?",
            max_steps=5,
            max_history_images=3,
        )
        assert ctx.max_history_images == 3


class TestContextManagerAddTurn:
    """Tests for ContextManager.add_turn method."""

    def test_add_turn_appends_to_trajectory(self) -> None:
        """Test that add_turn adds a turn to trajectory."""
        ctx = ContextManager(
            wsi_path="/slide.svs",
            question="Q?",
            max_steps=5,
        )
        response = StepResponse(
            reasoning="Found region",
            action=BoundingBoxAction(x=100, y=200, width=300, height=400),
        )
        ctx.add_turn(
            image_base64="thumb==",
            response=response,
        )
        assert len(ctx.trajectory.turns) == 1
        assert ctx.trajectory.turns[0].step_index == 0

    def test_add_turn_increments_step_index(self) -> None:
        """Test that step index increments with each turn."""
        ctx = ContextManager(
            wsi_path="/slide.svs",
            question="Q?",
            max_steps=5,
        )
        for i in range(3):
            response = StepResponse(
                reasoning=f"Step {i}",
                action=BoundingBoxAction(x=0, y=0, width=100, height=100),
            )
            ctx.add_turn(image_base64=f"img{i}==", response=response)

        assert ctx.trajectory.turns[0].step_index == 0
        assert ctx.trajectory.turns[1].step_index == 1
        assert ctx.trajectory.turns[2].step_index == 2

    def test_add_turn_with_region(self) -> None:
        """Test adding turn with region reference."""
        ctx = ContextManager(
            wsi_path="/slide.svs",
            question="Q?",
            max_steps=5,
        )
        response = StepResponse(
            reasoning="Crop",
            action=BoundingBoxAction(x=50, y=50, width=100, height=100),
        )
        region = Region(x=1000, y=2000, width=500, height=500)
        ctx.add_turn(
            image_base64="crop==",
            response=response,
            region=region,
        )
        assert ctx.trajectory.turns[0].region == region

    def test_add_turn_sets_final_answer(self) -> None:
        """Test that final answer action sets trajectory.final_answer."""
        ctx = ContextManager(
            wsi_path="/slide.svs",
            question="Q?",
            max_steps=5,
        )
        response = StepResponse(
            reasoning="Done",
            action=FinalAnswerAction(answer_text="Malignant"),
        )
        ctx.add_turn(image_base64="img==", response=response)
        assert ctx.trajectory.final_answer == "Malignant"


class TestContextManagerGetMessages:
    """Tests for ContextManager.get_messages method."""

    def test_get_messages_returns_system_and_user(self) -> None:
        """Test that get_messages includes system and user messages."""
        ctx = ContextManager(
            wsi_path="/slide.svs",
            question="What is this?",
            max_steps=5,
        )
        messages = ctx.get_messages(thumbnail_base64="thumb==")

        # Should have system + user messages
        assert len(messages) >= 2
        assert messages[0].role == "system"
        assert messages[1].role == "user"

    def test_get_messages_initial_includes_question(self) -> None:
        """Test that initial message includes the question."""
        ctx = ContextManager(
            wsi_path="/slide.svs",
            question="Is this malignant?",
            max_steps=5,
        )
        messages = ctx.get_messages(thumbnail_base64="thumb==")

        # Find text in user message
        user_msg = messages[1]
        text_content = next(c for c in user_msg.content if c.type == "text")
        assert "Is this malignant?" in (text_content.text or "")

    def test_get_messages_includes_thumbnail_image(self) -> None:
        """Test that initial message includes thumbnail image."""
        ctx = ContextManager(
            wsi_path="/slide.svs",
            question="Q?",
            max_steps=5,
        )
        messages = ctx.get_messages(thumbnail_base64="thumbnaildata==")

        user_msg = messages[1]
        image_contents = [c for c in user_msg.content if c.type == "image"]
        assert len(image_contents) == 1
        assert image_contents[0].image_base64 == "thumbnaildata=="

    def test_get_messages_alternates_user_assistant(self) -> None:
        """Test that messages alternate user/assistant after turns."""
        ctx = ContextManager(
            wsi_path="/slide.svs",
            question="Q?",
            max_steps=5,
        )
        # Add a turn
        response = StepResponse(
            reasoning="Zoom in",
            action=BoundingBoxAction(x=100, y=100, width=200, height=200),
        )
        ctx.add_turn(image_base64="thumb==", response=response)

        messages = ctx.get_messages(thumbnail_base64="thumb==")

        # Structure: system, user (initial), assistant (turn 0), user (next step)
        assert len(messages) == 4
        assert [m.role for m in messages] == [
            "system",
            "user",
            "assistant",
            "user",
        ]

    def test_get_messages_three_turns_structure(self) -> None:
        """Test message structure with 3 turns."""
        ctx = ContextManager(
            wsi_path="/slide.svs",
            question="Q?",
            max_steps=5,
        )
        # Add 3 turns
        for i in range(3):
            response = StepResponse(
                reasoning=f"Step {i}",
                action=BoundingBoxAction(x=i * 100, y=i * 100, width=100, height=100),
            )
            ctx.add_turn(image_base64=f"img{i}==", response=response)

        messages = ctx.get_messages(thumbnail_base64="thumb==")

        # Structure: system, user0, assistant0, user1, assistant1, user2,
        # assistant2, user3
        # (ready for the next LLM call after the 3rd crop).
        assert len(messages) == 8
        roles = [m.role for m in messages]
        assert roles == [
            "system",
            "user",
            "assistant",
            "user",
            "assistant",
            "user",
            "assistant",
            "user",
        ]

    def test_get_messages_includes_conch_scores_for_next_step(self) -> None:
        ctx = ContextManager(
            wsi_path="/slide.svs",
            question="Q?",
            max_steps=5,
            enable_conch=True,
        )
        response = StepResponse(
            reasoning="Score hypotheses with CONCH",
            action=ConchAction(hypotheses=["benign", "malignant"]),
        )
        ctx.add_turn(
            image_base64="img==",
            response=response,
            conch_scores=[0.2, 0.8],
        )

        messages = ctx.get_messages(thumbnail_base64="thumb==")

        assert [m.role for m in messages] == [
            "system",
            "user",
            "assistant",
            "user",
        ]
        user_msg = messages[-1]
        text_content = next(c for c in user_msg.content if c.type == "text")
        assert "CONCH" in (text_content.text or "")
        assert "malignant" in (text_content.text or "")

    def test_system_prompt_override_is_used(self) -> None:
        ctx = ContextManager(
            wsi_path="/slide.svs",
            question="Q?",
            max_steps=5,
            system_prompt="CUSTOM SYSTEM PROMPT",
        )
        messages = ctx.get_messages(thumbnail_base64="thumb==")
        system_msg = messages[0]
        text_content = next(c for c in system_msg.content if c.type == "text")
        assert "CUSTOM SYSTEM PROMPT" in (text_content.text or "")

    def test_enable_conch_adds_conch_to_system_prompt(self) -> None:
        ctx = ContextManager(
            wsi_path="/slide.svs",
            question="Q?",
            max_steps=5,
            enable_conch=True,
        )
        messages = ctx.get_messages(thumbnail_base64="thumb==")
        system_msg = messages[0]
        text_content = next(c for c in system_msg.content if c.type == "text")
        assert "conch" in (text_content.text or "").lower()


class TestContextManagerImagePruning:
    """Tests for image history pruning."""

    def test_no_pruning_when_limit_is_none(self) -> None:
        """Test all images kept when max_history_images is None."""
        ctx = ContextManager(
            wsi_path="/slide.svs",
            question="Q?",
            max_steps=10,
            max_history_images=None,
        )
        # Add 5 turns
        for i in range(5):
            response = StepResponse(
                reasoning=f"Step {i}",
                action=BoundingBoxAction(x=0, y=0, width=100, height=100),
            )
            ctx.add_turn(image_base64=f"img{i}==", response=response)

        messages = ctx.get_messages(thumbnail_base64="thumb==")

        # All images should be present
        image_count = sum(1 for m in messages for c in m.content if c.type == "image")
        # Thumbnail + 5 crop images
        assert image_count == 6

    def test_pruning_removes_old_images(self) -> None:
        """Test that old images are replaced with placeholder text."""
        ctx = ContextManager(
            wsi_path="/slide.svs",
            question="Q?",
            max_steps=10,
            max_history_images=2,
        )
        # Add 5 turns
        for i in range(5):
            response = StepResponse(
                reasoning=f"Step {i}",
                action=BoundingBoxAction(x=0, y=0, width=100, height=100),
            )
            ctx.add_turn(image_base64=f"img{i}==", response=response)

        messages = ctx.get_messages(thumbnail_base64="thumb==")

        # Should have: thumbnail (always) + last 2 crops = 3 images
        image_count = sum(1 for m in messages for c in m.content if c.type == "image")
        assert image_count == 3

    def test_pruning_keeps_thumbnail_always(self) -> None:
        """Test that thumbnail is never pruned."""
        ctx = ContextManager(
            wsi_path="/slide.svs",
            question="Q?",
            max_steps=10,
            max_history_images=1,
        )
        # Add 5 turns
        for i in range(5):
            response = StepResponse(
                reasoning=f"Step {i}",
                action=BoundingBoxAction(x=0, y=0, width=100, height=100),
            )
            ctx.add_turn(image_base64=f"img{i}==", response=response)

        messages = ctx.get_messages(thumbnail_base64="thumb==")

        # First user message should still have thumbnail
        user_msg = messages[1]
        image_contents = [c for c in user_msg.content if c.type == "image"]
        assert len(image_contents) == 1
        assert image_contents[0].image_base64 == "thumb=="

    def test_pruned_messages_have_placeholder_text(self) -> None:
        """Test that pruned images are replaced with placeholder."""
        ctx = ContextManager(
            wsi_path="/slide.svs",
            question="Q?",
            max_steps=10,
            max_history_images=1,
        )
        # Add 3 turns
        for i in range(3):
            response = StepResponse(
                reasoning=f"Step {i}",
                action=BoundingBoxAction(x=0, y=0, width=100, height=100),
            )
            ctx.add_turn(image_base64=f"img{i}==", response=response)

        messages = ctx.get_messages(thumbnail_base64="thumb==")

        # Find pruned message (should be the second user message, turn 1)
        # The placeholder should mention "removed"
        user_messages = [m for m in messages if m.role == "user"]
        # First user (initial) has thumbnail, second user (turn 1) should be pruned
        assert len(user_messages) > 1
        pruned_msg = user_messages[1]
        # Pruned message should have no images
        image_contents = [c for c in pruned_msg.content if c.type == "image"]
        assert len(image_contents) == 0
        # Should have placeholder text mentioning removal
        all_text = " ".join(
            c.text or "" for c in pruned_msg.content if c.type == "text"
        )
        assert "removed" in all_text.lower()


class TestContextManagerCurrentStep:
    """Tests for current step tracking."""

    def test_current_step_starts_at_one(self) -> None:
        """Test that current step starts at 1 (1-indexed)."""
        ctx = ContextManager(
            wsi_path="/slide.svs",
            question="Q?",
            max_steps=5,
        )
        assert ctx.current_step == 1

    def test_current_step_increments_after_add_turn(self) -> None:
        """Test that current step increments after adding turn."""
        ctx = ContextManager(
            wsi_path="/slide.svs",
            question="Q?",
            max_steps=5,
        )
        response = StepResponse(
            reasoning="Step",
            action=BoundingBoxAction(x=0, y=0, width=100, height=100),
        )
        ctx.add_turn(image_base64="img==", response=response)
        assert ctx.current_step == 2

    def test_is_final_step(self) -> None:
        """Test is_final_step property."""
        ctx = ContextManager(
            wsi_path="/slide.svs",
            question="Q?",
            max_steps=3,
        )
        assert not ctx.is_final_step
        # Add 2 turns
        for _ in range(2):
            response = StepResponse(
                reasoning="Step",
                action=BoundingBoxAction(x=0, y=0, width=100, height=100),
            )
            ctx.add_turn(image_base64="img==", response=response)
        # Now at step 3 of 3
        assert ctx.is_final_step
