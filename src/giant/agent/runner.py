"""GIANT Agent core navigation loop.

This module implements the main GIANTAgent class that orchestrates
autonomous WSI exploration per Algorithm 1 in the GIANT paper.

The agent:
1. Opens a WSI and generates a thumbnail with axis guides
2. Iteratively crops regions based on LLM decisions
3. Handles errors with retry logic
4. Enforces step limits and budget constraints
5. Returns structured results with full trajectory

Per Spec-09: GIANTAgent coordinates WSIReader, CropEngine, LLMProvider,
and ContextManager to autonomously explore a slide and answer a question.
"""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from giant.agent.context import ContextManager
from giant.agent.trajectory import Trajectory
from giant.config import settings
from giant.core.crop_engine import CropEngine
from giant.geometry.overlay import AxisGuideGenerator, OverlayService, OverlayStyle
from giant.geometry.primitives import Region, Size
from giant.geometry.validators import GeometryValidator, ValidationError
from giant.llm.protocol import (
    BoundingBoxAction,
    ConchAction,
    FinalAnswerAction,
    LLMError,
    LLMParseError,
    LLMProvider,
    LLMResponse,
    Message,
    MessageContent,
    StepResponse,
)
from giant.vision.conch import (
    ConchScorer,
    ConchUnavailableError,
    UnconfiguredConchScorer,
)
from giant.wsi.reader import WSIReader

if TYPE_CHECKING:
    from PIL import Image

logger = logging.getLogger(__name__)


# =============================================================================
# Error Templates
# =============================================================================

ERROR_FEEDBACK_TEMPLATE = """
Error: Your crop coordinates were invalid.
Requested region: x={x}, y={y}, width={width}, height={height}
Image bounds: width={max_width}, height={max_height}

Issues:
{issues}

Re-examine the axis guides on the thumbnail and provide valid Level-0 coordinates.
Your coordinates must satisfy:
- 0 <= x < {max_width}
- 0 <= y < {max_height}
- x + width <= {max_width}
- y + height <= {max_height}
"""

FORCE_ANSWER_TEMPLATE = """
You have reached the maximum number of navigation steps ({max_steps}).
Based on all the regions you have examined, you MUST now provide your final answer.

Review your observations:
{observation_summary}

Question: {question}

Provide your best answer using the `answer` action.
"""


# =============================================================================
# Result Models
# =============================================================================


class RunResult(BaseModel):
    """Result of a GIANTAgent navigation run.

    Attributes:
        answer: The final answer text (empty if run failed before answer).
        trajectory: Full navigation trajectory with all turns.
        total_tokens: Total tokens used across all LLM calls.
        total_cost: Total cost in USD across all LLM calls.
        success: Whether the run completed successfully with an answer.
        error_message: Description of failure if success=False.
    """

    answer: str = Field(default="", description="Final answer text")
    trajectory: Trajectory = Field(..., description="Full navigation trajectory")
    total_tokens: int = Field(default=0, ge=0, description="Total tokens used")
    total_cost: float = Field(default=0.0, ge=0.0, description="Total cost in USD")
    success: bool = Field(default=False, description="Whether run succeeded")
    error_message: str | None = Field(default=None, description="Error description")


@dataclass(frozen=True)
class _StepDecision:
    run_result: RunResult | None = None
    forced_summary: str | None = None
    break_to_force_answer: bool = False


# =============================================================================
# Agent Configuration
# =============================================================================


@dataclass
class AgentConfig:
    """Configuration for GIANTAgent behavior.

    Attributes:
        max_steps: Maximum navigation steps (T in Algorithm 1).
        max_retries: Maximum consecutive errors before termination.
        budget_usd: Optional cost limit (force answer if exceeded).
        thumbnail_size: Size for initial thumbnail generation.
        force_answer_retries: Retries for forcing answer at max steps.
        strict_font_check: If True, fail if axis label fonts are missing.
        enable_conch: If True, allow the model to invoke CONCH.
        conch_scorer: Optional scorer implementation for CONCH.
        system_prompt: Optional system prompt override (reproducibility).
    """

    max_steps: int = 20  # T=20 per GIANT paper (accuracy improves up to 20 iterations)
    max_retries: int = 3
    budget_usd: float | None = None
    thumbnail_size: int = 1024
    force_answer_retries: int = 3
    strict_font_check: bool = False
    enable_conch: bool = False
    conch_scorer: ConchScorer | None = None
    system_prompt: str | None = None


# =============================================================================
# GIANT Agent
# =============================================================================


@dataclass
class GIANTAgent:
    """GIANT Agent for autonomous WSI navigation.

    Orchestrates the navigation loop defined in Algorithm 1:
    1. Generate thumbnail with axis guides
    2. Iteratively request crop regions from LLM
    3. Execute crops and record trajectory
    4. Handle errors with retry/recovery
    5. Force final answer at step limit

    Usage:
        provider = OpenAIProvider()
        agent = GIANTAgent(
            wsi_path="/path/to/slide.svs",
            question="Is this malignant?",
            llm_provider=provider,
        )
        result = await agent.run()
    """

    wsi_path: str | Path
    question: str
    llm_provider: LLMProvider
    config: AgentConfig = field(default_factory=AgentConfig)

    # Internal state
    _context: ContextManager = field(init=False, repr=False)
    _reader: WSIReader = field(init=False, repr=False)
    _crop_engine: CropEngine = field(init=False, repr=False)
    _validator: GeometryValidator = field(init=False, repr=False)
    _overlay_service: OverlayService = field(init=False, repr=False)
    _thumbnail_base64: str = field(init=False, repr=False)
    _slide_bounds: Size = field(init=False, repr=False)
    _total_tokens: int = field(init=False, default=0, repr=False)
    _total_cost: float = field(init=False, default=0.0, repr=False)
    _consecutive_errors: int = field(init=False, default=0, repr=False)
    _conch_scorer: ConchScorer = field(init=False, repr=False)

    async def run(self) -> RunResult:
        """Execute the full navigation loop.

        This is the main entry point for the agent. It:
        1. Opens the WSI and creates the context manager
        2. Generates a thumbnail with axis guides (Turn 0)
        3. Loops through navigation steps
        4. Forces final answer at max steps
        5. Returns structured result

        Returns:
            RunResult with answer, trajectory, and metadata.

        Note:
            The WSI is opened and closed within this method.
            All errors are caught and returned in the result.
        """
        wsi_path_str = str(self.wsi_path)

        # Initialize components
        self._validator = GeometryValidator()
        overlay_style = OverlayStyle(strict_font_check=self.config.strict_font_check)
        self._overlay_service = OverlayService(
            generator=AxisGuideGenerator(style=overlay_style)
        )
        self._total_tokens = 0
        self._total_cost = 0.0
        self._consecutive_errors = 0
        self._conch_scorer = self.config.conch_scorer or UnconfiguredConchScorer()

        try:
            with WSIReader(wsi_path_str) as reader:
                self._reader = reader
                self._crop_engine = CropEngine(reader)

                # Get slide bounds for validation
                metadata = reader.get_metadata()
                self._slide_bounds = Size(width=metadata.width, height=metadata.height)

                # Initialize context manager
                provider_name = self._infer_provider_name()
                system_prompt = (
                    self.config.system_prompt
                    or settings.get_giant_system_prompt(provider=provider_name)
                )
                self._context = ContextManager(
                    wsi_path=wsi_path_str,
                    question=self.question,
                    max_steps=self.config.max_steps,
                    system_prompt=system_prompt,
                    enable_conch=self.config.enable_conch,
                )

                # Step 0: Generate thumbnail with axis guides
                self._thumbnail_base64 = self._generate_thumbnail(reader)

                # Populate visualization metadata
                self._context.trajectory.slide_width = self._slide_bounds.width
                self._context.trajectory.slide_height = self._slide_bounds.height
                self._context.trajectory.thumbnail_base64 = self._thumbnail_base64

                # Run navigation loop
                return await self._navigation_loop()

        except Exception as e:
            logger.exception("Agent run failed with exception")
            # Preserve partial trajectory if context was initialized
            trajectory = (
                self._context.trajectory
                if hasattr(self, "_context")
                else Trajectory(wsi_path=wsi_path_str, question=self.question)
            )
            return RunResult(
                answer="",
                trajectory=trajectory,
                total_tokens=self._total_tokens,
                total_cost=self._total_cost,
                success=False,
                error_message=f"Agent failed: {e}",
            )

    def _infer_provider_name(self) -> str | None:
        name = type(self.llm_provider).__name__.lower()
        if "openai" in name:
            return "openai"
        if "anthropic" in name:
            return "anthropic"
        return None

    async def _call_llm_step(
        self, messages: list[Message]
    ) -> tuple[LLMResponse | None, str | None]:
        try:
            response = await self.llm_provider.generate_response(messages)
            self._accumulate_usage(response)
        except (LLMError, LLMParseError) as e:
            logger.warning("LLM call failed: %s", e)
            self._consecutive_errors += 1
            if self._consecutive_errors >= self.config.max_retries:
                return (
                    None,
                    f"Max retries ({self.config.max_retries}) exceeded: {e}",
                )
            return None, None

        self._consecutive_errors = 0
        return response, None

    async def _navigation_loop(self) -> RunResult:
        """Execute the main navigation loop.

        Returns:
            RunResult from completed navigation.
        """
        forced_summary: str | None = None
        final_result: RunResult | None = None

        while self._context.current_step <= self.config.max_steps:
            # Check budget constraint
            if self._is_budget_exceeded():
                break

            # Get messages and make LLM call
            messages = self._context.get_messages(self._thumbnail_base64)

            response, fatal_error = await self._call_llm_step(messages)
            if fatal_error is not None:
                final_result = self._build_error_result(fatal_error)
                break
            if response is None:
                continue

            decision = await self._handle_step_action(response.step_response, messages)
            if decision.forced_summary is not None:
                forced_summary = decision.forced_summary
            if decision.run_result is not None:
                final_result = decision.run_result
                break
            if decision.break_to_force_answer:
                break

        # Force finalization (step limit reached or loop ended).
        if final_result is not None:
            return final_result
        if self._is_budget_exceeded():
            return await self._handle_budget_exceeded()
        return await self._force_final_answer(observation_summary=forced_summary)

    async def _handle_step_action(
        self, step_response: StepResponse, messages: list[Message]
    ) -> _StepDecision:
        action = step_response.action

        if isinstance(action, FinalAnswerAction):
            logger.warning(
                "Model returned answer at step %d/%d",
                self._context.current_step,
                self.config.max_steps,
            )
            return _StepDecision(run_result=self._handle_answer(step_response))

        if isinstance(action, BoundingBoxAction):
            return await self._handle_crop_action(step_response, action, messages)

        if isinstance(action, ConchAction):
            return await self._handle_conch_action(step_response, action)

        if self._context.is_final_step:
            return _StepDecision(break_to_force_answer=True)

        return _StepDecision()

    def _build_forced_summary_for_final_step(self, attempted_action: str) -> str:
        base_summary = self._build_observation_summary()
        note = (
            "\n(Note: You attempted to "
            f"{attempted_action} on the final step, but the step limit has been "
            "reached. You must answer now based on previous observations.)"
        )
        return base_summary + note

    async def _handle_crop_action(
        self,
        step_response: StepResponse,
        action: BoundingBoxAction,
        messages: list[Message],
    ) -> _StepDecision:
        if self._context.is_final_step:
            logger.warning(
                "Model returned crop at final step %d, forcing answer.",
                self._context.current_step,
            )
            forced_summary = self._build_forced_summary_for_final_step("crop")
            return _StepDecision(
                forced_summary=forced_summary,
                break_to_force_answer=True,
            )

        result = await self._handle_crop(step_response, action, messages)
        if result is not None:
            return _StepDecision(run_result=result)
        return _StepDecision()

    async def _handle_conch_action(
        self,
        step_response: StepResponse,
        action: ConchAction,
    ) -> _StepDecision:
        if self._context.is_final_step:
            logger.warning(
                "Model returned conch at final step %d, forcing answer.",
                self._context.current_step,
            )
            forced_summary = self._build_forced_summary_for_final_step("invoke CONCH")
            return _StepDecision(
                forced_summary=forced_summary,
                break_to_force_answer=True,
            )

        if not self.config.enable_conch:
            logger.warning(
                "Model requested CONCH but enable_conch is False (step %d).",
                self._context.current_step,
            )
            self._consecutive_errors += 1
            if self._consecutive_errors >= self.config.max_retries:
                return _StepDecision(
                    run_result=self._build_error_result(
                        "Model requested CONCH but tool is disabled"
                    )
                )
            return _StepDecision()

        result = await self._handle_conch(step_response, action)
        if result is not None:
            return _StepDecision(run_result=result)
        return _StepDecision()

    async def _handle_crop(
        self,
        step_response: StepResponse,
        action: BoundingBoxAction,
        messages: list[Message],
    ) -> RunResult | None:
        """Handle a crop action from the LLM.

        Args:
            step_response: The LLM's response.
            action: The bounding box action to execute.
            messages: Current message history for error feedback.

        Returns:
            RunResult if crop fails after retries, None on success.
        """
        region = Region(
            x=action.x,
            y=action.y,
            width=action.width,
            height=action.height,
        )

        # Validate bounds
        try:
            self._validator.validate(region, self._slide_bounds, strict=True)
        except ValidationError as e:
            logger.warning("Invalid crop region: %s", e)
            return await self._handle_invalid_region(action, messages, str(e))

        # Execute crop
        target_size = self.llm_provider.get_target_size()
        try:
            cropped = self._crop_engine.crop(region, target_size=target_size)
        except ValueError as e:
            logger.warning("Crop failed: %s", e)
            return await self._handle_invalid_region(action, messages, str(e))

        # Record turn
        self._context.add_turn(
            image_base64=cropped.base64_content,
            response=step_response,
            region=region,
        )

        logger.info(
            "Step %d: Cropped region (%d, %d, %d, %d)",
            self._context.current_step - 1,
            region.x,
            region.y,
            region.width,
            region.height,
        )

        return None

    async def _handle_conch(
        self,
        step_response: StepResponse,
        action: ConchAction,
    ) -> RunResult | None:
        """Handle a CONCH action by scoring hypotheses against current view."""
        observation_image = self._thumbnail_base64
        observation_region = None
        if self._context.trajectory.turns:
            last_turn = self._context.trajectory.turns[-1]
            observation_image = last_turn.image_base64
            observation_region = last_turn.region

        from PIL import Image  # noqa: PLC0415

        try:
            image_bytes = base64.b64decode(observation_image)
            pil_image = Image.open(BytesIO(image_bytes)).convert("RGB")
        except Exception as e:
            return self._build_error_result(f"Failed to decode observation image: {e}")

        try:
            scores = self._conch_scorer.score_hypotheses(
                pil_image,
                list(action.hypotheses),
            )
        except ConchUnavailableError as e:
            return self._build_error_result(str(e))
        except Exception as e:
            return self._build_error_result(f"CONCH scoring failed: {e}")

        if len(scores) != len(action.hypotheses):
            return self._build_error_result(
                "CONCH scorer returned a score list of unexpected length: "
                f"{len(scores)} != {len(action.hypotheses)}"
            )

        self._context.add_turn(
            image_base64=observation_image,
            response=step_response,
            region=observation_region,
            conch_scores=[float(s) for s in scores],
        )

        logger.info(
            "Step %d: CONCH scored %d hypotheses",
            self._context.current_step - 1,
            len(action.hypotheses),
        )

        return None

    async def _handle_invalid_region(
        self,
        action: BoundingBoxAction,
        messages: list[Message],
        error_detail: str,
    ) -> RunResult | None:
        """Handle invalid crop coordinates with iterative retry.

        Uses an iterative loop instead of recursion to handle retries.
        Each iteration asks the LLM for corrected coordinates, validates
        them, and either succeeds, continues retrying, or fails.

        Args:
            action: The invalid bounding box action.
            messages: Current message history (not mutated).
            error_detail: Description of the validation failure.

        Returns:
            RunResult if max retries exceeded or answer given, None on success.
        """
        current_action = action
        current_error = error_detail

        while True:
            self._consecutive_errors += 1

            if self._consecutive_errors >= self.config.max_retries:
                return self._build_error_result(
                    f"Max retries ({self.config.max_retries}) on invalid coordinates"
                )

            # Build error feedback message
            feedback = ERROR_FEEDBACK_TEMPLATE.format(
                x=current_action.x,
                y=current_action.y,
                width=current_action.width,
                height=current_action.height,
                max_width=self._slide_bounds.width,
                max_height=self._slide_bounds.height,
                issues=current_error,
            )

            # Add error feedback to original messages (not accumulating)
            error_message = Message(
                role="user",
                content=[MessageContent(type="text", text=feedback)],
            )
            messages_with_error = [*messages, error_message]

            try:
                response = await self.llm_provider.generate_response(
                    messages_with_error
                )
                self._accumulate_usage(response)
            except (LLMError, LLMParseError) as e:
                logger.warning("Retry LLM call failed: %s", e)
                self._consecutive_errors += 1
                if self._consecutive_errors >= self.config.max_retries:
                    return self._build_error_result(
                        f"Max retries ({self.config.max_retries}) exceeded: {e}"
                    )
                return None

            new_action = response.step_response.action

            if isinstance(new_action, FinalAnswerAction):
                # Success: answer ends the run, reset error counter
                self._consecutive_errors = 0
                return self._handle_answer(response.step_response)

            if isinstance(new_action, BoundingBoxAction):
                # Validate the new crop coordinates
                region = Region(
                    x=new_action.x,
                    y=new_action.y,
                    width=new_action.width,
                    height=new_action.height,
                )

                try:
                    self._validator.validate(region, self._slide_bounds, strict=True)
                except ValidationError as e:
                    # Invalid coordinates again, continue retry loop
                    logger.warning("Retry crop still invalid: %s", e)
                    current_action = new_action
                    current_error = str(e)
                    continue

                # Execute the crop
                target_size = self.llm_provider.get_target_size()
                try:
                    cropped = self._crop_engine.crop(region, target_size=target_size)
                except ValueError as e:
                    # Crop execution failed, continue retry loop
                    logger.warning("Retry crop execution failed: %s", e)
                    current_action = new_action
                    current_error = str(e)
                    continue

                # Success! Record turn and reset error counter
                self._context.add_turn(
                    image_base64=cropped.base64_content,
                    response=response.step_response,
                    region=region,
                )

                logger.info(
                    "Step %d: Cropped region (%d, %d, %d, %d) after retry",
                    self._context.current_step - 1,
                    region.x,
                    region.y,
                    region.width,
                    region.height,
                )

                self._consecutive_errors = 0
                return None

            # Unexpected action type - treat as no-op
            return None

    def _handle_answer(self, step_response: StepResponse) -> RunResult:
        """Handle a final answer action.

        Args:
            step_response: The response containing the answer.

        Returns:
            RunResult with the answer.
        """
        action = step_response.action
        assert isinstance(action, FinalAnswerAction)

        # Record the answer turn with the current observation image
        observation_image = self._thumbnail_base64
        observation_region = None
        if self._context.trajectory.turns:
            last_turn = self._context.trajectory.turns[-1]
            observation_image = last_turn.image_base64
            observation_region = last_turn.region

        self._context.add_turn(
            image_base64=observation_image,
            response=step_response,
            region=observation_region,
        )

        logger.info("Agent provided answer: %s", action.answer_text[:100])

        return RunResult(
            answer=action.answer_text,
            trajectory=self._context.trajectory,
            total_tokens=self._total_tokens,
            total_cost=self._total_cost,
            success=True,
            error_message=None,
        )

    async def _force_final_answer(
        self,
        *,
        observation_summary: str | None = None,
    ) -> RunResult:
        """Force the agent to provide a final answer.

        Called when max steps is reached. Retries up to force_answer_retries
        times if the model keeps trying to crop.

        Returns:
            RunResult with answer (success or error).
        """
        logger.info("Forcing final answer at max steps")

        # Build observation summary from trajectory
        summary = observation_summary or self._build_observation_summary()

        force_prompt = FORCE_ANSWER_TEMPLATE.format(
            max_steps=self.config.max_steps,
            observation_summary=summary,
            question=self.question,
        )

        for attempt in range(self.config.force_answer_retries):
            messages = self._context.get_messages(self._thumbnail_base64)
            force_message = Message(
                role="user",
                content=[MessageContent(type="text", text=force_prompt)],
            )
            messages_with_force = [*messages, force_message]

            try:
                response = await self.llm_provider.generate_response(
                    messages_with_force
                )
                self._accumulate_usage(response)
            except (LLMError, LLMParseError) as e:
                logger.warning("Force answer LLM call failed: %s", e)
                continue

            action = response.step_response.action

            if isinstance(action, FinalAnswerAction):
                return self._handle_answer(response.step_response)

            # Model still trying to crop, retry
            logger.warning(
                "Model attempted crop at force answer, attempt %d/%d",
                attempt + 1,
                self.config.force_answer_retries,
            )

        return self._build_error_result(
            f"Exceeded step limit after {self.config.force_answer_retries} retries"
        )

    async def _handle_budget_exceeded(self) -> RunResult:
        """Handle budget exceeded by forcing an answer.

        Returns:
            RunResult with success=False and budget error.
        """
        logger.warning(
            "Budget exceeded: $%.4f >= $%.4f",
            self._total_cost,
            self.config.budget_usd,
        )

        budget_note = (
            f"Budget reached: ${self._total_cost:.4f} >= ${self.config.budget_usd:.4f}."
        )
        summary = f"{budget_note}\n\n{self._build_observation_summary()}"

        # Try to get a final answer (explicitly noting budget reached)
        result = await self._force_final_answer(observation_summary=summary)

        # Mark as failure due to budget
        return RunResult(
            answer=result.answer,
            trajectory=result.trajectory,
            total_tokens=result.total_tokens,
            total_cost=result.total_cost,
            success=False,
            error_message="Budget exceeded",
        )

    def _is_budget_exceeded(self) -> bool:
        """Check if the cost budget has been exceeded."""
        if self.config.budget_usd is None:
            return False
        return self._total_cost >= self.config.budget_usd

    def _accumulate_usage(self, response: LLMResponse) -> None:
        """Accumulate token usage from a response."""
        self._total_tokens += response.usage.total_tokens
        self._total_cost += response.usage.cost_usd

    def _build_observation_summary(self) -> str:
        """Build a summary of observations for the force answer prompt."""
        if not self._context.trajectory.turns:
            return "No observations yet."

        lines = []
        for turn in self._context.trajectory.turns:
            region_str = ""
            if turn.region:
                r = turn.region
                region_str = f" at ({r.x}, {r.y}, {r.width}, {r.height})"
            reasoning = turn.response.reasoning
            lines.append(f"- Step {turn.step_index + 1}{region_str}: {reasoning}")

        return "\n".join(lines)

    def _build_error_result(self, error_message: str) -> RunResult:
        """Build an error result with current state."""
        return RunResult(
            answer="",
            trajectory=self._context.trajectory,
            total_tokens=self._total_tokens,
            total_cost=self._total_cost,
            success=False,
            error_message=error_message,
        )

    def _generate_thumbnail(self, reader: WSIReader) -> str:
        """Generate a thumbnail with axis guides.

        Args:
            reader: Open WSI reader.

        Returns:
            Base64-encoded JPEG thumbnail with axis guides.
        """
        max_size = (self.config.thumbnail_size, self.config.thumbnail_size)
        thumbnail = reader.get_thumbnail(max_size)
        metadata = reader.get_metadata()

        # Add axis guides
        navigable = self._overlay_service.create_navigable_thumbnail(
            thumbnail, metadata
        )

        # Encode to base64 JPEG
        return self._encode_image_base64(navigable)

    def _encode_image_base64(self, image: Image.Image, quality: int = 85) -> str:
        """Encode a PIL Image to base64 JPEG.

        Args:
            image: PIL Image to encode.
            quality: JPEG quality (1-100).

        Returns:
            Base64-encoded string.
        """
        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=quality)
        buffer.seek(0)
        return base64.b64encode(buffer.getvalue()).decode("ascii")
