"""Baseline inference utilities for GIANT (Spec-11/Spec-12).

Implements non-navigating baselines:
- Thumbnail baseline (single thumbnail, answer-only)
- Patch baseline (montage of random patches, answer-only)
"""

from __future__ import annotations

import base64
import math
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image

from giant.agent.runner import RunResult
from giant.agent.trajectory import Trajectory, Turn
from giant.llm.protocol import (
    FinalAnswerAction,
    LLMError,
    LLMParseError,
    LLMProvider,
    Message,
    MessageContent,
)


@dataclass(frozen=True)
class BaselineRequest:
    wsi_path: Path
    question: str
    image_base64: str
    media_type: str
    context_note: str


def encode_image_to_base64(image: Image.Image) -> tuple[str, str]:
    """Encode a PIL image to base64 (JPEG) and return (base64, media_type)."""
    buffer = BytesIO()
    image.convert("RGB").save(buffer, format="JPEG", quality=95)
    return base64.b64encode(buffer.getvalue()).decode("utf-8"), "image/jpeg"


def make_patch_collage(
    patches: list[Image.Image],
    *,
    patch_size: int,
    cols: int = 6,
    bg_color: tuple[int, int, int] = (0, 0, 0),
) -> Image.Image:
    """Create a single montage image from a list of patch images."""
    if not patches:
        raise ValueError("patches must not be empty")
    if patch_size <= 0:
        raise ValueError("patch_size must be > 0")
    if cols <= 0:
        raise ValueError("cols must be > 0")

    rows = math.ceil(len(patches) / cols)
    collage = Image.new("RGB", (cols * patch_size, rows * patch_size), color=bg_color)

    for idx, patch in enumerate(patches):
        row, col = divmod(idx, cols)
        x = col * patch_size
        y = row * patch_size
        collage.paste(patch.convert("RGB"), (x, y))

    return collage


async def run_baseline_answer(
    *,
    llm_provider: LLMProvider,
    request: BaselineRequest,
    max_attempts: int = 3,
) -> RunResult:
    """Run a single non-navigating baseline (thumbnail or patch montage)."""
    system_prompt = (
        "You are an expert computational pathologist.\n\n"
        "You will be given an image representation of a Whole Slide Image.\n"
        "You MUST provide your final answer using the `answer` action.\n"
        "You are not allowed to use the `crop` action in this mode."
    )

    base_user_text = (
        f"{request.context_note}\n\nQuestion: {request.question}\n\n"
        "Return your response as a StepResponse with action_type='answer'."
    )

    total_tokens = 0
    total_cost = 0.0
    last_error: str | None = None

    for attempt in range(max_attempts):
        attempt_note = ""
        if attempt > 0:
            attempt_note = (
                "\n\nIMPORTANT: Cropping is disabled. You MUST answer now using "
                "action_type='answer'."
            )

        messages = [
            Message(
                role="system",
                content=[MessageContent(type="text", text=system_prompt)],
            ),
            Message(
                role="user",
                content=[
                    MessageContent(type="text", text=base_user_text + attempt_note),
                    MessageContent(
                        type="image",
                        image_base64=request.image_base64,
                        media_type=request.media_type,
                    ),
                ],
            ),
        ]

        try:
            response = await llm_provider.generate_response(messages)
        except (LLMError, LLMParseError) as e:
            last_error = str(e)
            continue

        total_tokens += response.usage.total_tokens
        total_cost += response.usage.cost_usd

        step = response.step_response
        if isinstance(step.action, FinalAnswerAction):
            trajectory = Trajectory(
                wsi_path=str(request.wsi_path),
                question=request.question,
            )
            trajectory.turns.append(
                Turn(
                    step_index=0,
                    image_base64=request.image_base64,
                    response=step,
                    region=None,
                )
            )
            trajectory.final_answer = step.action.answer_text

            return RunResult(
                answer=step.action.answer_text,
                trajectory=trajectory,
                total_tokens=total_tokens,
                total_cost=total_cost,
                success=True,
                error_message=None,
            )

        last_error = "Model attempted crop in baseline mode"

    failure_trajectory = Trajectory(
        wsi_path=str(request.wsi_path),
        question=request.question,
    )
    return RunResult(
        answer="",
        trajectory=failure_trajectory,
        total_tokens=total_tokens,
        total_cost=total_cost,
        success=False,
        error_message=last_error or "Baseline failed",
    )
