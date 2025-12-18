"""Context manager for GIANT navigation.

Manages conversation state and message construction for the LLM.
Implements Spec-08 Conversation Context Manager.

The ContextManager:
- Tracks the full navigation trajectory
- Constructs properly formatted messages for the LLM
- Optionally prunes old images to manage context window size
"""

from __future__ import annotations

from dataclasses import dataclass, field

from giant.agent.trajectory import Trajectory, Turn
from giant.geometry.primitives import Region
from giant.llm.protocol import (
    FinalAnswerAction,
    Message,
    MessageContent,
    StepResponse,
)
from giant.prompts.builder import PromptBuilder


@dataclass
class ContextManager:
    """Manages navigation context and message history.

    Responsible for:
    - Tracking the agent's trajectory (observations, reasoning, actions)
    - Constructing LLM messages with proper alternation (user/assistant)
    - Pruning old images when history limit is exceeded

    Usage:
        ctx = ContextManager(
            wsi_path="/slide.svs",
            question="Is this malignant?",
            max_steps=5,
        )
        ctx.add_turn(image_base64=thumbnail, response=response)
        messages = ctx.get_messages(thumbnail_base64=thumbnail)
    """

    wsi_path: str
    question: str
    max_steps: int
    max_history_images: int | None = None

    trajectory: Trajectory = field(init=False)
    _prompt_builder: PromptBuilder = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Initialize trajectory and prompt builder."""
        self.trajectory = Trajectory(
            wsi_path=self.wsi_path,
            question=self.question,
        )
        self._prompt_builder = PromptBuilder()

    @property
    def current_step(self) -> int:
        """Get the current step number (1-indexed).

        Returns:
            Current step number starting from 1.
        """
        return len(self.trajectory.turns) + 1

    @property
    def is_final_step(self) -> bool:
        """Check if we're at the final step.

        Returns:
            True if current step equals max_steps.
        """
        return self.current_step == self.max_steps

    def add_turn(
        self,
        image_base64: str,
        response: StepResponse,
        region: Region | None = None,
    ) -> None:
        """Add a navigation turn to the trajectory.

        Args:
            image_base64: Base64-encoded image for this step.
            response: The model's reasoning and action.
            region: The region that was cropped (None for thumbnail).
        """
        turn = Turn(
            step_index=len(self.trajectory.turns),
            image_base64=image_base64,
            response=response,
            region=region,
        )
        self.trajectory.turns.append(turn)

        # Set final answer if this was an answer action
        if isinstance(response.action, FinalAnswerAction):
            self.trajectory.final_answer = response.action.answer_text

    def get_messages(self, thumbnail_base64: str) -> list[Message]:
        """Construct the full message history for the LLM.

        Builds a properly formatted conversation with:
        1. System message (navigation instructions)
        2. Initial user message (question + thumbnail)
        3. Alternating assistant/user messages for each turn

        Args:
            thumbnail_base64: Base64-encoded thumbnail image.

        Returns:
            List of Messages ready for the LLM provider.
        """
        messages: list[Message] = []

        # 1. System message
        messages.append(self._prompt_builder.build_system_message())

        # 2. Initial user message with question and thumbnail
        messages.append(
            self._prompt_builder.build_user_message(
                question=self.question,
                step=1,
                max_steps=self.max_steps,
                context_images=[thumbnail_base64],
            )
        )

        # 3. Add turns as alternating assistant/user messages
        for i, turn in enumerate(self.trajectory.turns):
            # Assistant message: reasoning + action
            messages.append(self._build_assistant_message(turn))

            # If not the last turn, add user message for next step
            if i < len(self.trajectory.turns) - 1:
                next_turn = self.trajectory.turns[i + 1]
                messages.append(
                    self._build_user_message_for_turn(
                        turn=next_turn,
                        step=i + 2,  # 1-indexed, +1 for next step
                    )
                )
            elif i == len(self.trajectory.turns) - 1:
                # Last turn: no additional user message needed
                pass

        # Apply image pruning if configured
        if self.max_history_images is not None:
            messages = self._apply_image_pruning(messages, thumbnail_base64)

        return messages

    def _build_assistant_message(self, turn: Turn) -> Message:
        """Build assistant message from a turn.

        Args:
            turn: The turn to build message from.

        Returns:
            Message with role='assistant'.
        """
        # Format the assistant response as text
        action = turn.response.action
        if hasattr(action, "action_type"):
            if action.action_type == "crop":
                action_text = (
                    f"crop(x={action.x}, y={action.y}, "
                    f"width={action.width}, height={action.height})"
                )
            else:
                action_text = f'answer("{action.answer_text}")'
        else:
            action_text = str(action)

        text = f"Reasoning: {turn.response.reasoning}\n\nAction: {action_text}"

        return Message(
            role="assistant",
            content=[MessageContent(type="text", text=text)],
        )

    def _build_user_message_for_turn(self, turn: Turn, step: int) -> Message:
        """Build user message for a subsequent turn.

        Args:
            turn: The turn containing the crop image.
            step: The step number (1-indexed).

        Returns:
            Message with role='user' containing crop image.
        """
        # Format region string if available
        last_region = None
        if turn.region is not None:
            r = turn.region
            last_region = f"({r.x}, {r.y}, {r.width}, {r.height})"

        return self._prompt_builder.build_user_message(
            question=self.question,
            step=step,
            max_steps=self.max_steps,
            context_images=[turn.image_base64],
            last_region=last_region,
        )

    def _apply_image_pruning(
        self,
        messages: list[Message],
        thumbnail_base64: str,
    ) -> list[Message]:
        """Apply image pruning to keep context window manageable.

        Keeps:
        - Thumbnail (always, in first user message)
        - Last N crop images (where N = max_history_images)

        Replaces pruned images with placeholder text.

        Args:
            messages: List of messages to prune.
            thumbnail_base64: Thumbnail to always keep.

        Returns:
            Pruned message list.
        """
        if self.max_history_images is None:
            return messages

        # Count how many crop images we have (excluding thumbnail)
        crop_count = len(self.trajectory.turns)
        if crop_count <= self.max_history_images:
            return messages

        # Calculate which turns to prune (keep last N)
        turns_to_keep = set(range(crop_count - self.max_history_images, crop_count))

        # Prune images from user messages (after the initial one)
        pruned_messages: list[Message] = []
        user_msg_index = 0

        for msg in messages:
            if msg.role == "user":
                if user_msg_index == 0:
                    # First user message - keep thumbnail
                    pruned_messages.append(msg)
                else:
                    # Subsequent user messages - check if should prune
                    # user_msg[k] contains turn[k].image for k > 0
                    turn_index = user_msg_index
                    if turn_index not in turns_to_keep:
                        # Prune: replace image with placeholder
                        pruned_messages.append(
                            self._prune_images_from_message(msg, turn_index)
                        )
                    else:
                        pruned_messages.append(msg)
                user_msg_index += 1
            else:
                pruned_messages.append(msg)

        return pruned_messages

    def _prune_images_from_message(self, msg: Message, step_index: int) -> Message:
        """Replace images in a message with placeholder text.

        Args:
            msg: Message to prune images from.
            step_index: Step index for placeholder text.

        Returns:
            New message with images replaced by placeholder.
        """
        new_content: list[MessageContent] = []

        for content in msg.content:
            if content.type == "image":
                # Replace with placeholder text
                placeholder = (
                    f"[Image from Step {step_index + 1} removed to save context]"
                )
                new_content.append(MessageContent(type="text", text=placeholder))
            else:
                new_content.append(content)

        return Message(role=msg.role, content=new_content)
