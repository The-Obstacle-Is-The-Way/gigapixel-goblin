"""Tests for giant.prompts.builder module.

TDD tests for PromptBuilder following Spec-07 requirements.
"""

import pytest

from giant.prompts.builder import PromptBuilder


class TestPromptBuilderSystemMessage:
    """Tests for system message construction."""

    def test_system_message_has_correct_role(self) -> None:
        """Test that system message has role='system'."""
        builder = PromptBuilder()
        message = builder.build_system_message()
        assert message.role == "system"

    def test_system_message_has_text_content(self) -> None:
        """Test that system message contains text content."""
        builder = PromptBuilder()
        message = builder.build_system_message()
        assert len(message.content) == 1
        assert message.content[0].type == "text"
        assert message.content[0].text is not None

    def test_system_message_contains_giant_identity(self) -> None:
        """Test that system prompt identifies as GIANT."""
        builder = PromptBuilder()
        message = builder.build_system_message()
        text = message.content[0].text or ""
        assert "GIANT" in text
        assert "pathologist" in text.lower()

    def test_system_message_explains_coordinate_system(self) -> None:
        """Test that system prompt explains Level-0 coordinates."""
        builder = PromptBuilder()
        message = builder.build_system_message()
        text = message.content[0].text or ""
        assert "Level-0" in text or "level-0" in text.lower()

    def test_system_message_mentions_axis_guides(self) -> None:
        """Test that system prompt mentions axis guides."""
        builder = PromptBuilder()
        message = builder.build_system_message()
        text = message.content[0].text or ""
        assert "axis" in text.lower() and "guide" in text.lower()

    def test_system_message_describes_crop_tool(self) -> None:
        """Test that system prompt describes the crop tool."""
        builder = PromptBuilder()
        message = builder.build_system_message()
        text = message.content[0].text or ""
        assert "crop" in text.lower()
        # Should mention coordinates
        assert "x" in text.lower() and "y" in text.lower()

    def test_system_message_describes_answer_tool(self) -> None:
        """Test that system prompt describes the answer tool."""
        builder = PromptBuilder()
        message = builder.build_system_message()
        text = message.content[0].text or ""
        assert "answer" in text.lower()


class TestPromptBuilderUserMessage:
    """Tests for user message construction."""

    def test_user_message_has_correct_role(self) -> None:
        """Test that user message has role='user'."""
        builder = PromptBuilder()
        message = builder.build_user_message(
            question="What is the diagnosis?",
            step=1,
            max_steps=5,
            context_images=[],
        )
        assert message.role == "user"

    def test_user_message_includes_question(self) -> None:
        """Test that user message includes the question."""
        builder = PromptBuilder()
        question = "Is this tissue malignant?"
        message = builder.build_user_message(
            question=question,
            step=1,
            max_steps=5,
            context_images=[],
        )
        # Find text content
        text_content = next(c for c in message.content if c.type == "text")
        assert question in (text_content.text or "")

    def test_user_message_includes_step_status(self) -> None:
        """Test that user message includes step X of Y status."""
        builder = PromptBuilder()
        message = builder.build_user_message(
            question="What is the diagnosis?",
            step=2,
            max_steps=7,
            context_images=[],
        )
        text_content = next(c for c in message.content if c.type == "text")
        text = text_content.text or ""
        # Should mention step 2 and max 7
        assert "2" in text
        assert "7" in text

    def test_user_message_includes_remaining_crops(self) -> None:
        """Test that user message shows remaining crops."""
        builder = PromptBuilder()
        message = builder.build_user_message(
            question="What is the diagnosis?",
            step=1,
            max_steps=5,
            context_images=[],
        )
        text_content = next(c for c in message.content if c.type == "text")
        text = text_content.text or ""
        # Step 1 of 5 means 4 crops remaining (paper: "at most T-1 crops")
        assert "4" in text and "remaining" in text.lower()

    def test_user_message_includes_images(self) -> None:
        """Test that user message includes context images."""
        builder = PromptBuilder()
        # Fake base64 images
        images = ["base64image1==", "base64image2=="]
        message = builder.build_user_message(
            question="What is the diagnosis?",
            step=1,
            max_steps=5,
            context_images=images,
        )
        # Should have text + images
        image_contents = [c for c in message.content if c.type == "image"]
        assert len(image_contents) == 2
        assert image_contents[0].image_base64 == "base64image1=="
        assert image_contents[1].image_base64 == "base64image2=="

    def test_user_message_initial_step_instruction(self) -> None:
        """Test that initial step has crop instruction."""
        builder = PromptBuilder()
        message = builder.build_user_message(
            question="What is the diagnosis?",
            step=1,
            max_steps=5,
            context_images=[],
        )
        text_content = next(c for c in message.content if c.type == "text")
        text = text_content.text or ""
        # Per spec: "For Steps 1..{max_steps - 1} you MUST use crop"
        assert "crop" in text.lower()

    def test_user_message_final_step_forces_answer(self) -> None:
        """Test that final step requires answer."""
        builder = PromptBuilder()
        message = builder.build_user_message(
            question="What is the diagnosis?",
            step=5,
            max_steps=5,
            context_images=[],
        )
        text_content = next(c for c in message.content if c.type == "text")
        text = text_content.text or ""
        # Final step should mention must answer
        assert "answer" in text.lower()
        # Should indicate this is final
        assert "must" in text.lower() or "final" in text.lower()


class TestPromptBuilderSubsequentSteps:
    """Tests for subsequent step message variations."""

    def test_subsequent_step_mentions_last_action(self) -> None:
        """Test that subsequent steps can mention last action."""
        builder = PromptBuilder()
        message = builder.build_user_message(
            question="What is the diagnosis?",
            step=2,
            max_steps=5,
            context_images=["base64crop=="],
            last_region="(1000, 2000, 500, 500)",
        )
        text_content = next(c for c in message.content if c.type == "text")
        text = text_content.text or ""
        # Should mention the last region
        assert "1000" in text or "crop" in text.lower()

    def test_image_media_type_is_jpeg(self) -> None:
        """Test that image content has correct media type."""
        builder = PromptBuilder()
        message = builder.build_user_message(
            question="What is the diagnosis?",
            step=1,
            max_steps=5,
            context_images=["base64image=="],
        )
        image_content = next(c for c in message.content if c.type == "image")
        assert image_content.media_type == "image/jpeg"


class TestPromptBuilderEdgeCases:
    """Tests for edge cases and validation."""

    def test_empty_question_raises(self) -> None:
        """Test that empty question raises ValueError."""
        builder = PromptBuilder()
        with pytest.raises(ValueError, match="question"):
            builder.build_user_message(
                question="",
                step=1,
                max_steps=5,
                context_images=[],
            )

    def test_step_exceeds_max_raises(self) -> None:
        """Test that step > max_steps raises ValueError."""
        builder = PromptBuilder()
        with pytest.raises(ValueError, match="step"):
            builder.build_user_message(
                question="What is the diagnosis?",
                step=6,
                max_steps=5,
                context_images=[],
            )

    def test_zero_step_raises(self) -> None:
        """Test that step 0 raises ValueError."""
        builder = PromptBuilder()
        with pytest.raises(ValueError, match="step"):
            builder.build_user_message(
                question="What is the diagnosis?",
                step=0,
                max_steps=5,
                context_images=[],
            )

    def test_max_steps_less_than_one_raises(self) -> None:
        """Test that max_steps < 1 raises ValueError."""
        builder = PromptBuilder()
        with pytest.raises(ValueError, match="max_steps"):
            builder.build_user_message(
                question="What is the diagnosis?",
                step=1,
                max_steps=0,
                context_images=[],
            )
