"""CLI smoke tests for Spec-01 toolchain wiring."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from giant.cli.main import app

runner = CliRunner()


def test_help_shown_without_subcommand() -> None:
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "Commands" in result.stdout


def test_version_command_outputs_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.startswith("giant ")


def test_benchmark_smoke_writes_output() -> None:
    with runner.isolated_filesystem():
        dataset_dir = Path("data/multipathqa")
        dataset_dir.mkdir(parents=True)
        (dataset_dir / "MultiPathQA.csv").write_text(
            "benchmark_name,question_id\npanda,1\ngtex,2\ngtex,3\n",
            encoding="utf-8",
        )

        output_dir = Path("results")
        result = runner.invoke(
            app,
            ["benchmark", str(dataset_dir), "--output-dir", str(output_dir)],
        )
        assert result.exit_code == 0

        out_path = output_dir / "benchmark_smoke.json"
        assert out_path.exists()

        payload = json.loads(out_path.read_text(encoding="utf-8"))
        expected_total_rows = 3
        expected_gtex = 2
        expected_panda = 1
        assert payload["smoke"] is True
        assert payload["total_rows"] == expected_total_rows
        assert payload["by_benchmark"]["gtex"] == expected_gtex
        assert payload["by_benchmark"]["panda"] == expected_panda


def test_benchmark_requires_metadata_csv() -> None:
    with runner.isolated_filesystem():
        dataset_dir = Path("data/multipathqa")
        dataset_dir.mkdir(parents=True)
        output_dir = Path("results")

        result = runner.invoke(
            app,
            ["benchmark", str(dataset_dir), "--output-dir", str(output_dir)],
        )
        assert result.exit_code != 0
        assert "Expected metadata CSV" in result.output
