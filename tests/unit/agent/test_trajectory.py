"""Tests for giant.agent.trajectory module.

TDD tests for Turn and Trajectory data models following Spec-08.
"""

import json

from giant.agent.trajectory import Trajectory, Turn
from giant.geometry.primitives import Region
from giant.llm.protocol import BoundingBoxAction, FinalAnswerAction, StepResponse


class TestTurnModel:
    """Tests for Turn data model."""

    def test_turn_creation_with_crop_action(self) -> None:
        """Test creating a turn with crop action."""
        response = StepResponse(
            reasoning="I see a suspicious region",
            action=BoundingBoxAction(x=100, y=200, width=300, height=400),
        )
        turn = Turn(
            step_index=0,
            image_base64="base64data==",
            response=response,
            region=None,
        )
        assert turn.step_index == 0
        assert turn.image_base64 == "base64data=="
        assert turn.response.reasoning == "I see a suspicious region"
        assert turn.region is None

    def test_turn_creation_with_region(self) -> None:
        """Test creating a turn with a region reference."""
        response = StepResponse(
            reasoning="Zooming in",
            action=BoundingBoxAction(x=50, y=50, width=100, height=100),
        )
        region = Region(x=1000, y=2000, width=500, height=500)
        turn = Turn(
            step_index=1,
            image_base64="cropdata==",
            response=response,
            region=region,
        )
        assert turn.region is not None
        assert turn.region.x == 1000

    def test_turn_serialization(self) -> None:
        """Test that Turn serializes to JSON."""
        response = StepResponse(
            reasoning="Analysis",
            action=FinalAnswerAction(answer_text="Benign"),
        )
        turn = Turn(
            step_index=2,
            image_base64="data==",
            response=response,
        )
        json_str = turn.model_dump_json()
        assert "step_index" in json_str
        assert "Benign" in json_str


class TestTrajectoryModel:
    """Tests for Trajectory data model."""

    def test_trajectory_creation(self) -> None:
        """Test creating an empty trajectory."""
        trajectory = Trajectory(
            wsi_path="/path/to/slide.svs",
            question="Is this malignant?",
        )
        assert trajectory.wsi_path == "/path/to/slide.svs"
        assert trajectory.question == "Is this malignant?"
        assert trajectory.turns == []
        assert trajectory.final_answer is None

    def test_trajectory_with_turns(self) -> None:
        """Test trajectory with multiple turns."""
        turn1 = Turn(
            step_index=0,
            image_base64="thumb==",
            response=StepResponse(
                reasoning="Start",
                action=BoundingBoxAction(x=100, y=100, width=200, height=200),
            ),
        )
        turn2 = Turn(
            step_index=1,
            image_base64="crop1==",
            response=StepResponse(
                reasoning="End",
                action=FinalAnswerAction(answer_text="Benign"),
            ),
            region=Region(x=100, y=100, width=200, height=200),
        )
        trajectory = Trajectory(
            wsi_path="/slide.svs",
            question="Diagnosis?",
            turns=[turn1, turn2],
            final_answer="Benign",
        )
        assert len(trajectory.turns) == 2
        assert trajectory.final_answer == "Benign"

    def test_trajectory_serialization_to_json(self) -> None:
        """Test that Trajectory serializes to valid JSON."""
        trajectory = Trajectory(
            wsi_path="/slide.svs",
            question="What is this?",
            turns=[
                Turn(
                    step_index=0,
                    image_base64="thumb==",
                    response=StepResponse(
                        reasoning="Looking",
                        action=BoundingBoxAction(x=0, y=0, width=100, height=100),
                    ),
                ),
            ],
        )
        json_str = trajectory.model_dump_json()
        # Should be valid JSON
        parsed = json.loads(json_str)
        assert parsed["wsi_path"] == "/slide.svs"
        assert len(parsed["turns"]) == 1

    def test_trajectory_deserialization_from_json(self) -> None:
        """Test that Trajectory can be loaded from JSON."""
        json_data = {
            "wsi_path": "/test.svs",
            "question": "Test?",
            "turns": [
                {
                    "step_index": 0,
                    "image_base64": "data==",
                    "response": {
                        "reasoning": "Test",
                        "action": {"action_type": "answer", "answer_text": "Done"},
                    },
                    "region": None,
                }
            ],
            "final_answer": "Done",
        }
        trajectory = Trajectory.model_validate(json_data)
        assert trajectory.wsi_path == "/test.svs"
        assert trajectory.final_answer == "Done"
        assert len(trajectory.turns) == 1
