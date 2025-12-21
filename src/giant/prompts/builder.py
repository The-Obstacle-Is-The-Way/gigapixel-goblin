"""Prompt builder for GIANT navigation.

Constructs properly formatted messages for the LLM from templates.
Implements Spec-07 Navigation Prompt Engineering.
"""

from giant.llm.protocol import Message, MessageContent
from giant.prompts.templates import (
    FINAL_STEP_PROMPT,
    INITIAL_USER_PROMPT,
    SUBSEQUENT_USER_PROMPT,
    SYSTEM_PROMPT,
)


class PromptBuilder:
    """Builds prompts for GIANT navigation steps.

    Responsible for:
    - Constructing the system message with navigation instructions
    - Building user messages with dynamic step state
    - Including images in the proper format

    Usage:
        builder = PromptBuilder()
        system_msg = builder.build_system_message()
        user_msg = builder.build_user_message(
            question="Is this tissue malignant?",
            step=1,
            max_steps=20,  # T=20 per GIANT paper
            context_images=[thumbnail_base64],
        )
    """

    def build_system_message(self) -> Message:
        """Build the system message with navigation instructions.

        Returns:
            Message with role='system' containing the GIANT system prompt.
        """
        return Message(
            role="system",
            content=[
                MessageContent(
                    type="text",
                    text=SYSTEM_PROMPT,
                )
            ],
        )

    def build_user_message(
        self,
        question: str,
        step: int,
        max_steps: int,
        context_images: list[str],
        last_region: str | None = None,
    ) -> Message:
        """Build the user message for a navigation step.

        Args:
            question: The diagnostic question to answer.
            step: Current step number (1-indexed).
            max_steps: Total number of steps allowed.
            context_images: List of base64-encoded images to include.
            last_region: String description of the last cropped region
                (e.g., "(1000, 2000, 500, 500)") for subsequent steps.

        Returns:
            Message with role='user' containing text and images.

        Raises:
            ValueError: If inputs are invalid (empty question, step out of range).
        """
        # Validate inputs
        if not question or not question.strip():
            raise ValueError("question must not be empty")
        if max_steps < 1:
            raise ValueError("max_steps must be at least 1")
        if step < 1:
            raise ValueError("step must be at least 1")
        if step > max_steps:
            raise ValueError(f"step ({step}) cannot exceed max_steps ({max_steps})")

        # Build text content
        text = self._build_prompt_text(question, step, max_steps, last_region)

        # Build message content list
        content: list[MessageContent] = [
            MessageContent(type="text", text=text),
        ]

        # Add images
        for image_base64 in context_images:
            content.append(
                MessageContent(
                    type="image",
                    image_base64=image_base64,
                    media_type="image/jpeg",
                )
            )

        return Message(role="user", content=content)

    def _build_prompt_text(
        self,
        question: str,
        step: int,
        max_steps: int,
        last_region: str | None,
    ) -> str:
        """Build the appropriate prompt text based on step state.

        Args:
            question: The diagnostic question.
            step: Current step (1-indexed).
            max_steps: Total steps allowed.
            last_region: Description of last cropped region (for subsequent steps).

        Returns:
            Formatted prompt text string.
        """
        remaining_crops = max_steps - step

        # Final step - must answer
        if step == max_steps:
            return FINAL_STEP_PROMPT.format(
                question=question,
                step=step,
                max_steps=max_steps,
            )

        # Initial step (step 1)
        if step == 1:
            return INITIAL_USER_PROMPT.format(
                question=question,
                step=step,
                max_steps=max_steps,
                remaining_crops=remaining_crops,
            )

        # Subsequent steps (2 to max_steps-1)
        return SUBSEQUENT_USER_PROMPT.format(
            question=question,
            step=step,
            max_steps=max_steps,
            remaining_crops=remaining_crops,
            last_region=last_region or "unknown",
        )
