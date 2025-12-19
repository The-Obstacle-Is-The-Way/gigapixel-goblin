"""Checkpoint and resume logic for benchmark runs (Spec-10).

Provides functionality to:
- Save intermediate results during long evaluation runs
- Resume interrupted runs from the last checkpoint
- Track progress and avoid re-running completed items
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from giant.data.schemas import BenchmarkResult

logger = logging.getLogger(__name__)

_DEFAULT_LIKE_VALUES: tuple[object, ...] = (
    None,
    False,
    0,
    0.0,
    "",
    (),
    [],
    {},
)


def _is_default_like(value: object) -> bool:
    return value in _DEFAULT_LIKE_VALUES


def _configs_equivalent(existing: dict[str, Any], new: dict[str, Any]) -> bool:
    """Compare configs while allowing additive default-like keys.

    This lets newer versions resume older checkpoints when new config keys are
    introduced with default values (e.g., False/None/0), without weakening the
    guardrail against resuming with materially different settings.
    """
    all_keys = set(existing) | set(new)
    for key in all_keys:
        if key in existing and key in new:
            if existing[key] != new[key]:
                return False
            continue

        if key in existing:
            if not _is_default_like(existing[key]):
                return False
            continue

        if not _is_default_like(new[key]):
            return False

    return True


class CheckpointState(BaseModel):
    """State saved at each checkpoint.

    Attributes:
        run_id: Unique identifier for this evaluation run.
        benchmark_name: Name of the benchmark being evaluated.
        completed_ids: Set of item IDs that have been completed.
        results: List of BenchmarkResult for completed items.
        config: Configuration used for this run (for validation on resume).
    """

    run_id: str
    benchmark_name: str
    completed_ids: set[str] = Field(default_factory=set)
    results: list[BenchmarkResult] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)


class CheckpointManager:
    """Manages checkpointing for resumable benchmark runs.

    Usage:
        manager = CheckpointManager(checkpoint_dir="/results/checkpoints")
        state = manager.load_or_create("run-001", "tcga")

        for item in items:
            if item.benchmark_id in state.completed_ids:
                continue  # Already done

            result = run_agent(item)
            state.results.append(result)
            state.completed_ids.add(item.benchmark_id)
            manager.save(state)
    """

    def __init__(self, checkpoint_dir: Path | str) -> None:
        """Initialize checkpoint manager.

        Args:
            checkpoint_dir: Directory to store checkpoint files.
        """
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def _checkpoint_path(self, run_id: str) -> Path:
        """Get the checkpoint file path for a run."""
        run_id_path = Path(run_id)
        if (
            run_id_path.is_absolute()
            or ".." in run_id_path.parts
            or run_id_path.name != run_id
        ):
            raise ValueError(
                f"Invalid run_id {run_id!r}: must be a simple filename (no traversal)."
            )
        return self.checkpoint_dir / f"{run_id}.checkpoint.json"

    def exists(self, run_id: str) -> bool:
        """Check if a checkpoint exists for the given run ID."""
        return self._checkpoint_path(run_id).exists()

    def load(self, run_id: str) -> CheckpointState | None:
        """Load checkpoint state if it exists.

        Args:
            run_id: Unique identifier for the evaluation run.

        Returns:
            CheckpointState if checkpoint exists, None otherwise.
        """
        path = self._checkpoint_path(run_id)
        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text())
            # Handle set serialization
            data["completed_ids"] = set(data.get("completed_ids", []))
            return CheckpointState.model_validate(data)
        except Exception as e:
            logger.warning("Failed to load checkpoint %s: %s", path, e)
            return None

    def load_or_create(
        self,
        run_id: str,
        benchmark_name: str,
        config: dict[str, Any] | None = None,
    ) -> CheckpointState:
        """Load existing checkpoint or create a new one.

        Args:
            run_id: Unique identifier for the evaluation run.
            benchmark_name: Name of the benchmark.
            config: Configuration for this run (used for validation).

        Returns:
            Loaded or newly created CheckpointState.
        """
        existing = self.load(run_id)
        if existing is not None:
            if existing.benchmark_name != benchmark_name:
                raise ValueError(
                    f"Checkpoint {run_id!r} is for benchmark "
                    f"{existing.benchmark_name!r}, not {benchmark_name!r}. "
                    "Use a new run_id or delete the checkpoint."
                )
            if (
                config is not None
                and existing.config
                and not _configs_equivalent(existing.config, config)
            ):
                raise ValueError(
                    f"Checkpoint {run_id!r} config mismatch. "
                    "Refusing to resume with different settings. "
                    "Use a new run_id or delete the checkpoint."
                )
            logger.info(
                "Resuming from checkpoint: %d/%d items completed",
                len(existing.completed_ids),
                len(existing.results),
            )
            return existing

        return CheckpointState(
            run_id=run_id,
            benchmark_name=benchmark_name,
            config=config or {},
        )

    def save(self, state: CheckpointState) -> None:
        """Save checkpoint state to disk.

        Args:
            state: Current checkpoint state to save.
        """
        path = self._checkpoint_path(state.run_id)

        # Convert to dict and handle set serialization
        data = state.model_dump()
        data["completed_ids"] = list(data["completed_ids"])

        # Write atomically via temp file (replace() is atomic on both POSIX and Windows)
        temp_path = path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(data, indent=2))
        temp_path.replace(path)

        logger.debug(
            "Checkpoint saved: %d items completed",
            len(state.completed_ids),
        )

    def delete(self, run_id: str) -> bool:
        """Delete a checkpoint file.

        Args:
            run_id: Unique identifier for the evaluation run.

        Returns:
            True if checkpoint was deleted, False if it didn't exist.
        """
        path = self._checkpoint_path(run_id)
        if path.exists():
            path.unlink()
            return True
        return False
