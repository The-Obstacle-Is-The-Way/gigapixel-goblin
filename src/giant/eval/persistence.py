"""Persistence utilities for benchmark evaluation (Spec-10).

Centralizes filesystem writes for:
- Evaluation results JSON
- Per-item run trajectories

This module exists to keep orchestration and execution logic free of I/O details.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from giant.agent.runner import RunResult
from giant.utils.logging import get_logger

if TYPE_CHECKING:
    from giant.eval.runner import EvaluationResults

logger = get_logger(__name__)

_SAFE_FILENAME_COMPONENT_RE = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True)
class ResultsPersistence:
    """Handles saving evaluation artifacts."""

    output_dir: Path

    @staticmethod
    def validate_run_id(run_id: str) -> None:
        run_id_path = Path(run_id)
        if (
            run_id_path.is_absolute()
            or ".." in run_id_path.parts
            or run_id_path.name != run_id
        ):
            raise ValueError(
                f"Invalid run_id {run_id!r}: must be a simple filename "
                "(no path traversal)."
            )

    @staticmethod
    def safe_filename_component(value: str) -> str:
        """Return a filesystem-safe component for filenames."""
        safe = _SAFE_FILENAME_COMPONENT_RE.sub("_", value).strip("._-")
        return safe or "item"

    def save_trajectory(
        self,
        *,
        run_result: RunResult,
        item_id: str,
        run_idx: int,
    ) -> str:
        """Save a single run trajectory to JSON and return the path as a string."""
        trajectories_dir = self.output_dir / "trajectories"
        trajectories_dir.mkdir(exist_ok=True)

        safe_item_id = self.safe_filename_component(item_id)
        filename = f"{safe_item_id}_run{run_idx}.json"
        path = trajectories_dir / filename

        trajectory_data = run_result.trajectory.model_dump()
        path.write_text(json.dumps(trajectory_data, indent=2))

        return str(path)

    def save_results(self, results: EvaluationResults) -> Path:
        """Save final evaluation results and return the output path."""
        results_path = self.output_dir / f"{results.run_id}_results.json"
        results_path.write_text(results.model_dump_json(indent=2))
        logger.info("Results saved to %s", results_path)
        return results_path
