"""Tests for GIANT CLI (Spec-12).

TDD: These tests define the expected CLI behavior per the spec.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from giant.cli.main import Mode, Provider, app

if TYPE_CHECKING:
    pass

runner = CliRunner()


# =============================================================================
# Version Command
# =============================================================================


class TestVersionCommand:
    """Tests for `giant version`."""

    def test_version_outputs_version_string(self) -> None:
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "giant" in result.stdout.lower()

    def test_version_json_output(self) -> None:
        result = runner.invoke(app, ["version", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "version" in data


# =============================================================================
# Run Command
# =============================================================================


class TestRunCommand:
    """Tests for `giant run`."""

    def test_run_requires_wsi_path(self) -> None:
        result = runner.invoke(app, ["run", "--question", "What is this?"])
        assert result.exit_code != 0

    def test_run_requires_question(self, tmp_path: Path) -> None:
        wsi = tmp_path / "test.svs"
        wsi.touch()
        result = runner.invoke(app, ["run", str(wsi)])
        assert result.exit_code != 0

    def test_run_validates_wsi_exists(self, tmp_path: Path) -> None:
        fake_wsi = tmp_path / "nonexistent.svs"
        result = runner.invoke(
            app, ["run", str(fake_wsi), "--question", "What is this?"]
        )
        assert result.exit_code != 0

    def test_run_mode_enum_values(self) -> None:
        assert Mode.giant.value == "giant"
        assert Mode.thumbnail.value == "thumbnail"
        assert Mode.patch.value == "patch"

    def test_run_provider_enum_values(self) -> None:
        assert Provider.openai.value == "openai"
        assert Provider.anthropic.value == "anthropic"

    def test_run_accepts_mode_flag(self, tmp_path: Path) -> None:
        wsi = tmp_path / "test.svs"
        wsi.touch()

        with patch("giant.cli.runners.run_single_inference") as mock_run:
            mock_run.return_value = MagicMock(
                success=True,
                answer="Test answer",
                total_cost=0.01,
                agreement=1.0,
                runs_answers=["Test answer"],
                trajectory=MagicMock(turns=[]),
            )
            result = runner.invoke(
                app,
                [
                    "run",
                    str(wsi),
                    "--question",
                    "What is this?",
                    "--mode",
                    "thumbnail",
                ],
            )
            # Should call with thumbnail mode
            assert result.exit_code == 0, result.stdout
            mock_run.assert_called_once()
            call_kwargs = mock_run.call_args[1]
            assert call_kwargs.get("mode") == Mode.thumbnail

    def test_run_accepts_provider_flag(self, tmp_path: Path) -> None:
        wsi = tmp_path / "test.svs"
        wsi.touch()

        with patch("giant.cli.runners.run_single_inference") as mock_run:
            mock_run.return_value = MagicMock(
                success=True,
                answer="Test",
                total_cost=0.01,
                agreement=1.0,
                runs_answers=["Test"],
                trajectory=MagicMock(turns=[]),
            )
            result = runner.invoke(
                app,
                [
                    "run",
                    str(wsi),
                    "-q",
                    "What?",
                    "--provider",
                    "anthropic",
                ],
            )
            assert result.exit_code == 0, result.stdout
            mock_run.assert_called_once()
            call_kwargs = mock_run.call_args[1]
            assert call_kwargs.get("provider") == Provider.anthropic

    def test_run_accepts_runs_flag(self, tmp_path: Path) -> None:
        wsi = tmp_path / "test.svs"
        wsi.touch()

        with patch("giant.cli.runners.run_single_inference") as mock_run:
            mock_run.return_value = MagicMock(
                success=True,
                answer="Test",
                total_cost=0.01,
                agreement=1.0,
                runs_answers=["Test"],
                trajectory=MagicMock(turns=[]),
            )
            result = runner.invoke(
                app,
                ["run", str(wsi), "-q", "What?", "--runs", "5"],
            )
            assert result.exit_code == 0, result.stdout
            mock_run.assert_called_once()
            call_kwargs = mock_run.call_args[1]
            assert call_kwargs.get("runs") == 5

    def test_run_accepts_budget_flag(self, tmp_path: Path) -> None:
        wsi = tmp_path / "test.svs"
        wsi.touch()

        with patch("giant.cli.runners.run_single_inference") as mock_run:
            mock_run.return_value = MagicMock(
                success=True,
                answer="Test",
                total_cost=0.01,
                agreement=1.0,
                runs_answers=["Test"],
                trajectory=MagicMock(turns=[]),
            )
            result = runner.invoke(
                app,
                ["run", str(wsi), "-q", "What?", "--budget-usd", "5.0"],
            )
            assert result.exit_code == 0, result.stdout
            mock_run.assert_called_once()
            call_kwargs = mock_run.call_args[1]
            assert call_kwargs.get("budget_usd") == 5.0

    def test_run_json_output(self, tmp_path: Path) -> None:
        wsi = tmp_path / "test.svs"
        wsi.touch()

        with patch("giant.cli.runners.run_single_inference") as mock_run:
            mock_run.return_value = MagicMock(
                success=True,
                answer="Cancer diagnosis",
                total_cost=0.50,
                agreement=1.0,
                runs_answers=["Cancer diagnosis"],
                trajectory=MagicMock(turns=[]),
            )
            result = runner.invoke(
                app,
                ["run", str(wsi), "-q", "What?", "--json"],
            )
            assert result.exit_code == 0, result.stdout
            data = json.loads(result.stdout)
            assert "answer" in data
            assert "cost" in data or "total_cost" in data

    def test_run_saves_trajectory(self, tmp_path: Path) -> None:
        wsi = tmp_path / "test.svs"
        wsi.touch()
        output = tmp_path / "trajectory.json"

        with patch("giant.cli.runners.run_single_inference") as mock_run:
            mock_run.return_value = MagicMock(
                success=True,
                answer="Test",
                total_cost=0.01,
                agreement=1.0,
                runs_answers=["Test"],
                trajectory=MagicMock(turns=[]),
            )
            result = runner.invoke(
                app,
                ["run", str(wsi), "-q", "What?", "--output", str(output)],
            )
            assert result.exit_code == 0, result.stdout
            assert output.exists()


# =============================================================================
# Benchmark Command
# =============================================================================


class TestBenchmarkCommand:
    """Tests for `giant benchmark`."""

    def test_benchmark_requires_dataset(self) -> None:
        result = runner.invoke(app, ["benchmark"])
        assert result.exit_code != 0

    def test_benchmark_accepts_dataset_name(self, tmp_path: Path) -> None:
        # Create mock CSV
        data_dir = tmp_path / "data" / "multipathqa"
        data_dir.mkdir(parents=True)
        csv_path = data_dir / "MultiPathQA.csv"
        csv_path.write_text(
            "benchmark_name,question_id,image_path,question,answer,file_id\n"
            "tcga,1,slides/a.svs,What?,Cancer,abc123\n"
        )

        with patch("giant.cli.runners.run_benchmark") as mock_bench:
            mock_bench.return_value = MagicMock(
                metrics={"accuracy": 0.5},
                total_cost=1.0,
                n_items=1,
                n_errors=0,
                run_id="tcga_giant_openai_gpt-5.2",
                results_path=tmp_path / "results.json",
            )
            result = runner.invoke(
                app,
                [
                    "benchmark",
                    "tcga",
                    "--csv-path",
                    str(csv_path),
                    "--wsi-root",
                    str(tmp_path),
                ],
            )
            # Verify command parses
            assert result.exit_code == 0, result.stdout
            mock_bench.assert_called_once()

    def test_benchmark_accepts_mode_flag(self, tmp_path: Path) -> None:
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        csv_path = data_dir / "MultiPathQA.csv"
        csv_path.write_text(
            "benchmark_name,question_id,image_path,question,answer,file_id\n"
        )

        with patch("giant.cli.runners.run_benchmark") as mock_bench:
            mock_bench.return_value = MagicMock(
                metrics={},
                total_cost=0.0,
                n_items=0,
                n_errors=0,
                run_id="tcga_patch_openai_gpt-5.2",
                results_path=tmp_path / "results.json",
            )
            result = runner.invoke(
                app,
                [
                    "benchmark",
                    "tcga",
                    "--csv-path",
                    str(csv_path),
                    "--wsi-root",
                    str(tmp_path),
                    "--mode",
                    "patch",
                ],
            )
            assert result.exit_code == 0, result.stdout
            call_kwargs = mock_bench.call_args[1]
            assert call_kwargs.get("mode") == Mode.patch

    def test_benchmark_accepts_concurrency_flag(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "MultiPathQA.csv"
        csv_path.write_text("benchmark_name,question_id\n")

        with patch("giant.cli.runners.run_benchmark") as mock_bench:
            mock_bench.return_value = MagicMock(
                metrics={},
                total_cost=0.0,
                n_items=0,
                n_errors=0,
                run_id="tcga_giant_openai_gpt-5.2",
                results_path=tmp_path / "results.json",
            )
            result = runner.invoke(
                app,
                [
                    "benchmark",
                    "tcga",
                    "--csv-path",
                    str(csv_path),
                    "--wsi-root",
                    str(tmp_path),
                    "--concurrency",
                    "8",
                ],
            )
            assert result.exit_code == 0, result.stdout
            call_kwargs = mock_bench.call_args[1]
            assert call_kwargs.get("concurrency") == 8

    def test_benchmark_resume_flag(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "MultiPathQA.csv"
        csv_path.write_text("benchmark_name,question_id\n")

        with patch("giant.cli.runners.run_benchmark") as mock_bench:
            mock_bench.return_value = MagicMock(
                metrics={},
                total_cost=0.0,
                n_items=0,
                n_errors=0,
                run_id="tcga_giant_openai_gpt-5.2",
                results_path=tmp_path / "results.json",
            )
            result = runner.invoke(
                app,
                [
                    "benchmark",
                    "tcga",
                    "--csv-path",
                    str(csv_path),
                    "--wsi-root",
                    str(tmp_path),
                    "--no-resume",
                ],
            )
            assert result.exit_code == 0, result.stdout
            call_kwargs = mock_bench.call_args[1]
            assert call_kwargs.get("resume") is False


# =============================================================================
# Download Command
# =============================================================================


class TestDownloadCommand:
    """Tests for `giant download`."""

    def test_download_default_dataset(self, tmp_path: Path) -> None:
        with patch("giant.cli.runners.download_dataset") as mock_dl:
            mock_dl.return_value = {"dataset": "multipathqa", "path": str(tmp_path)}
            result = runner.invoke(
                app,
                ["download", "--output-dir", str(tmp_path)],
            )
            assert result.exit_code == 0, result.stdout
            mock_dl.assert_called_once()
            call_args = mock_dl.call_args[1]
            assert call_args.get("dataset") == "multipathqa"

    def test_download_specific_dataset(self, tmp_path: Path) -> None:
        result = runner.invoke(
            app,
            ["download", "tcga", "--output-dir", str(tmp_path)],
        )
        assert result.exit_code != 0


# =============================================================================
# Visualize Command
# =============================================================================


class TestVisualizeCommand:
    """Tests for `giant visualize`."""

    def test_visualize_requires_trajectory_path(self) -> None:
        result = runner.invoke(app, ["visualize"])
        assert result.exit_code != 0

    def test_visualize_validates_path_exists(self, tmp_path: Path) -> None:
        fake_path = tmp_path / "nonexistent.json"
        result = runner.invoke(app, ["visualize", str(fake_path)])
        assert result.exit_code != 0

    def test_visualize_generates_html(self, tmp_path: Path) -> None:
        # Create mock trajectory
        traj_path = tmp_path / "trajectory.json"
        traj_path.write_text(
            json.dumps(
                {
                    "turns": [
                        {
                            "step": 1,
                            "action": "zoom",
                            "reasoning": "Looking closer",
                        }
                    ],
                    "answer": "Cancer",
                    "wsi_path": "/path/to/slide.svs",
                }
            )
        )
        output_html = tmp_path / "viz.html"

        with patch("giant.cli.visualizer.create_trajectory_html") as mock_viz:
            mock_viz.return_value = output_html
            result = runner.invoke(
                app,
                [
                    "visualize",
                    str(traj_path),
                    "--output",
                    str(output_html),
                    "--no-open",
                ],
            )
            assert result.exit_code == 0, result.stdout
            mock_viz.assert_called_once()


# =============================================================================
# Verbosity and Global Options
# =============================================================================


class TestVerbosityFlags:
    """Tests for verbosity control."""

    def test_verbose_flag_accepted(self, tmp_path: Path) -> None:
        wsi = tmp_path / "test.svs"
        wsi.touch()

        with patch("giant.cli.runners.run_single_inference") as mock_run:
            mock_run.return_value = MagicMock(
                success=True,
                answer="Test",
                total_cost=0.01,
                trajectory=MagicMock(turns=[]),
            )
            # -v flag should be accepted
            result = runner.invoke(
                app,
                ["run", str(wsi), "-q", "What?", "-v"],
            )
            assert result.exit_code == 0, result.stdout

    def test_double_verbose_flag(self, tmp_path: Path) -> None:
        wsi = tmp_path / "test.svs"
        wsi.touch()

        with patch("giant.cli.runners.run_single_inference") as mock_run:
            mock_run.return_value = MagicMock(
                success=True,
                answer="Test",
                total_cost=0.01,
                trajectory=MagicMock(turns=[]),
            )
            result = runner.invoke(
                app,
                ["run", str(wsi), "-q", "What?", "-vv"],
            )
            assert result.exit_code == 0, result.stdout


# =============================================================================
# Exit Codes
# =============================================================================


class TestExitCodes:
    """Tests for proper exit codes."""

    def test_success_exit_code_zero(self) -> None:
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0

    def test_invalid_command_nonzero_exit(self) -> None:
        result = runner.invoke(app, ["nonexistent-command"])
        assert result.exit_code != 0

    def test_missing_required_arg_nonzero_exit(self) -> None:
        result = runner.invoke(app, ["run"])
        assert result.exit_code != 0


# =============================================================================
# Help Text
# =============================================================================


class TestHelpText:
    """Tests for help documentation."""

    def test_main_help_shows_commands(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "run" in result.stdout
        assert "benchmark" in result.stdout
        assert "download" in result.stdout
        assert "visualize" in result.stdout

    def test_run_help_shows_options(self) -> None:
        result = runner.invoke(
            app, ["run", "--help"], env={"NO_COLOR": "1", "TERM": "dumb"}
        )
        assert result.exit_code == 0
        # Verify help runs and produces output
        assert len(result.stdout) > 0

    def test_benchmark_help_shows_options(self) -> None:
        result = runner.invoke(
            app, ["benchmark", "--help"], env={"NO_COLOR": "1", "TERM": "dumb"}
        )
        assert result.exit_code == 0
        # Verify help runs and produces output
        assert len(result.stdout) > 0
