"""Trajectory models for GIANT navigation.

Data models for tracking the agent's navigation history. These models
provide serializable representations of the navigation session for
visualization, analysis, and debugging.

Per Spec-08:
- Turn stores a single step's observation, reasoning, and action
- Trajectory stores the full navigation history
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from giant.geometry.primitives import Region
from giant.llm.protocol import StepResponse


class Turn(BaseModel):
    """A single navigation turn in the agent's trajectory.

    Represents one step of the navigation process including the image
    observed, the model's reasoning, and the action taken.

    Attributes:
        step_index: Zero-indexed step number in the trajectory.
        image_base64: Base64-encoded image observed at this step.
        response: The model's reasoning and action for this step.
        region: The region that was cropped to produce this view
            (None for initial thumbnail).
    """

    step_index: int = Field(..., ge=0, description="Zero-indexed step number")
    image_base64: str = Field(..., description="Base64-encoded image")
    response: StepResponse = Field(..., description="Model's reasoning and action")
    region: Region | None = Field(
        default=None,
        description="Region that was cropped (None for thumbnail)",
    )


class Trajectory(BaseModel):
    """Complete navigation trajectory for a WSI analysis session.

    Stores the full history of observations, reasoning, and actions
    taken by the agent. Can be serialized to JSON for visualization
    and analysis.

    Attributes:
        wsi_path: Path to the Whole Slide Image being analyzed.
        question: The diagnostic question being answered.
        turns: List of navigation turns in chronological order.
        final_answer: The agent's final answer (if completed).
    """

    wsi_path: str = Field(..., description="Path to the WSI file")
    question: str = Field(..., description="Diagnostic question")
    turns: list[Turn] = Field(default_factory=list, description="Navigation turns")
    final_answer: str | None = Field(
        default=None,
        description="Final answer (if completed)",
    )
