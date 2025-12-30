"""Tests for giant.eval.resumable module (Spec-10)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from giant.data.schemas import BenchmarkResult
from giant.eval.resumable import CheckpointManager, CheckpointState


@pytest.fixture
def temp_checkpoint_dir(tmp_path: Path) -> Path:
    """Create a temporary checkpoint directory."""
    return tmp_path / "checkpoints"


@pytest.fixture
def checkpoint_manager(temp_checkpoint_dir: Path) -> CheckpointManager:
    """Create a checkpoint manager."""
    return CheckpointManager(temp_checkpoint_dir)


class TestCheckpointState:
    """Tests for CheckpointState model."""

    def test_create_empty_state(self) -> None:
        """Test creating an empty checkpoint state."""
        state = CheckpointState(
            run_id="test-001",
            benchmark_name="tcga",
        )
        assert state.run_id == "test-001"
        assert state.benchmark_name == "tcga"
        assert len(state.completed_ids) == 0
        assert len(state.results) == 0

    def test_state_with_results(self) -> None:
        """Test checkpoint state with results."""
        result = BenchmarkResult(
            item_id="TCGA-001",
            prediction="Lung cancer",
            predicted_label=1,
            truth_label=1,
            correct=True,
            trajectory_file="/results/TCGA-001.json",
        )
        state = CheckpointState(
            run_id="test-001",
            benchmark_name="tcga",
            completed_ids={"TCGA-001"},
            results=[result],
        )
        assert "TCGA-001" in state.completed_ids
        assert len(state.results) == 1


class TestCheckpointManager:
    """Tests for CheckpointManager."""

    def test_creates_directory(self, temp_checkpoint_dir: Path) -> None:
        """Test that manager creates checkpoint directory."""
        CheckpointManager(temp_checkpoint_dir)
        assert temp_checkpoint_dir.exists()

    def test_exists_returns_false_for_new(
        self, checkpoint_manager: CheckpointManager
    ) -> None:
        """Test exists returns False for non-existent checkpoint."""
        assert checkpoint_manager.exists("non-existent") is False

    def test_load_returns_none_for_new(
        self, checkpoint_manager: CheckpointManager
    ) -> None:
        """Test load returns None for non-existent checkpoint."""
        assert checkpoint_manager.load("non-existent") is None

    def test_save_and_load(self, checkpoint_manager: CheckpointManager) -> None:
        """Test saving and loading a checkpoint."""
        state = CheckpointState(
            run_id="test-001",
            benchmark_name="tcga",
            completed_ids={"item-1", "item-2"},
            results=[
                BenchmarkResult(
                    item_id="item-1",
                    prediction="answer1",
                    truth_label=1,
                    correct=True,
                    trajectory_file="/test.json",
                ),
            ],
            config={"max_steps": 20},
        )

        checkpoint_manager.save(state)
        assert checkpoint_manager.exists("test-001")

        loaded = checkpoint_manager.load("test-001")
        assert loaded is not None
        assert loaded.run_id == "test-001"
        assert loaded.benchmark_name == "tcga"
        assert loaded.completed_ids == {"item-1", "item-2"}
        assert len(loaded.results) == 1
        assert loaded.config == {"max_steps": 20}

    def test_load_or_create_new(self, checkpoint_manager: CheckpointManager) -> None:
        """Test load_or_create creates new state if none exists."""
        state = checkpoint_manager.load_or_create(
            "new-run",
            "panda",
            config={"runs_per_item": 5},
        )
        assert state.run_id == "new-run"
        assert state.benchmark_name == "panda"
        assert len(state.completed_ids) == 0
        assert state.config == {"runs_per_item": 5}

    def test_load_or_create_existing(
        self, checkpoint_manager: CheckpointManager
    ) -> None:
        """Test load_or_create loads existing state."""
        # Save a state first
        state = CheckpointState(
            run_id="existing-run",
            benchmark_name="gtex",
            completed_ids={"item-1"},
        )
        checkpoint_manager.save(state)

        # Load it back
        loaded = checkpoint_manager.load_or_create(
            "existing-run",
            "gtex",
        )
        assert loaded.completed_ids == {"item-1"}

    def test_load_or_create_existing_benchmark_mismatch_raises(
        self, checkpoint_manager: CheckpointManager
    ) -> None:
        state = CheckpointState(
            run_id="mismatch-benchmark",
            benchmark_name="tcga",
            config={"max_steps": 20},
        )
        checkpoint_manager.save(state)

        with pytest.raises(ValueError, match="is for benchmark"):
            checkpoint_manager.load_or_create(
                "mismatch-benchmark",
                "gtex",
                config={"max_steps": 20},
            )

    def test_load_or_create_existing_config_mismatch_raises(
        self, checkpoint_manager: CheckpointManager
    ) -> None:
        state = CheckpointState(
            run_id="mismatch-config",
            benchmark_name="tcga",
            config={"max_steps": 20},
        )
        checkpoint_manager.save(state)

        with pytest.raises(ValueError, match="config mismatch"):
            checkpoint_manager.load_or_create(
                "mismatch-config",
                "tcga",
                config={"max_steps": 10},
            )

    def test_load_or_create_existing_model_mismatch_raises(
        self, checkpoint_manager: CheckpointManager
    ) -> None:
        state = CheckpointState(
            run_id="mismatch-model",
            benchmark_name="tcga",
            model_name="gpt-5.2",
            provider_name="OpenAIProvider",
        )
        checkpoint_manager.save(state)

        with pytest.raises(ValueError, match="model/provider mismatch"):
            checkpoint_manager.load_or_create(
                "mismatch-model",
                "tcga",
                model_name="claude-sonnet-4-5-20250929",
                provider_name="AnthropicProvider",
            )

    def test_load_or_create_sets_missing_model_metadata(
        self, checkpoint_manager: CheckpointManager
    ) -> None:
        state = CheckpointState(
            run_id="missing-model-metadata",
            benchmark_name="tcga",
        )
        checkpoint_manager.save(state)

        loaded = checkpoint_manager.load_or_create(
            "missing-model-metadata",
            "tcga",
            model_name="gpt-5.2",
            provider_name="OpenAIProvider",
        )
        assert loaded.model_name == "gpt-5.2"
        assert loaded.provider_name == "OpenAIProvider"

    def test_load_or_create_allows_added_default_like_keys(
        self, checkpoint_manager: CheckpointManager
    ) -> None:
        state = CheckpointState(
            run_id="added-default-keys",
            benchmark_name="tcga",
            config={"max_steps": 20},
        )
        checkpoint_manager.save(state)

        loaded = checkpoint_manager.load_or_create(
            "added-default-keys",
            "tcga",
            config={"max_steps": 20, "strict_font_check": False},
        )
        assert loaded.run_id == "added-default-keys"

    def test_load_or_create_new_non_default_key_raises(
        self, checkpoint_manager: CheckpointManager
    ) -> None:
        state = CheckpointState(
            run_id="added-non-default-keys",
            benchmark_name="tcga",
            config={"max_steps": 20},
        )
        checkpoint_manager.save(state)

        with pytest.raises(ValueError, match="config mismatch"):
            checkpoint_manager.load_or_create(
                "added-non-default-keys",
                "tcga",
                config={"max_steps": 20, "strict_font_check": True},
            )

    def test_delete_existing(self, checkpoint_manager: CheckpointManager) -> None:
        """Test deleting an existing checkpoint."""
        state = CheckpointState(run_id="to-delete", benchmark_name="tcga")
        checkpoint_manager.save(state)
        assert checkpoint_manager.exists("to-delete")

        result = checkpoint_manager.delete("to-delete")
        assert result is True
        assert checkpoint_manager.exists("to-delete") is False

    def test_delete_nonexistent(self, checkpoint_manager: CheckpointManager) -> None:
        """Test deleting a non-existent checkpoint."""
        result = checkpoint_manager.delete("non-existent")
        assert result is False

    def test_atomic_save(
        self, checkpoint_manager: CheckpointManager, temp_checkpoint_dir: Path
    ) -> None:
        """Test that save is atomic (no partial writes)."""
        state = CheckpointState(
            run_id="atomic-test",
            benchmark_name="tcga",
            completed_ids={"item-1"},
        )
        checkpoint_manager.save(state)

        # Verify file exists and no temp file remains
        checkpoint_path = temp_checkpoint_dir / "atomic-test.checkpoint.json"
        temp_path = temp_checkpoint_dir / "atomic-test.checkpoint.tmp"

        assert checkpoint_path.exists()
        assert not temp_path.exists()

        # Verify content is valid JSON
        data = json.loads(checkpoint_path.read_text())
        assert data["run_id"] == "atomic-test"

    def test_preserves_set_across_save_load(
        self, checkpoint_manager: CheckpointManager
    ) -> None:
        """Test that completed_ids set is preserved across save/load."""
        state = CheckpointState(
            run_id="set-test",
            benchmark_name="tcga",
            completed_ids={"a", "b", "c"},
        )
        checkpoint_manager.save(state)

        loaded = checkpoint_manager.load("set-test")
        assert loaded is not None
        assert isinstance(loaded.completed_ids, set)
        assert loaded.completed_ids == {"a", "b", "c"}
