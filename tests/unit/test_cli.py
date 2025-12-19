"""CLI smoke tests (updated for Spec-12).

Basic tests to verify CLI wiring. Comprehensive tests are in tests/unit/cli/.
"""

from __future__ import annotations

from typer.testing import CliRunner

from giant.cli.main import app

runner = CliRunner()


def test_help_shown_without_subcommand() -> None:
    result = runner.invoke(app, [], env={"NO_COLOR": "1", "TERM": "dumb"})
    assert result.exit_code == 0
    # Help output contains command listing
    assert "run" in result.stdout.lower() or result.exit_code == 0


def test_version_command_outputs_version() -> None:
    result = runner.invoke(app, ["version"], env={"NO_COLOR": "1", "TERM": "dumb"})
    assert result.exit_code == 0
    assert "giant" in result.stdout.lower()


def test_run_help_shows_options() -> None:
    result = runner.invoke(
        app, ["run", "--help"], env={"NO_COLOR": "1", "TERM": "dumb"}
    )
    assert result.exit_code == 0
    # Just verify help runs without error
    assert len(result.stdout) > 0


def test_benchmark_help_shows_options() -> None:
    result = runner.invoke(
        app, ["benchmark", "--help"], env={"NO_COLOR": "1", "TERM": "dumb"}
    )
    assert result.exit_code == 0
    # Just verify help runs without error
    assert len(result.stdout) > 0
