"""CLI smoke tests (updated for Spec-12).

Basic tests to verify CLI wiring. Comprehensive tests are in tests/unit/cli/.
"""

from __future__ import annotations

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


def test_run_help_shows_options() -> None:
    result = runner.invoke(app, ["run", "--help"])
    assert result.exit_code == 0
    assert "--question" in result.stdout
    assert "--mode" in result.stdout


def test_benchmark_help_shows_options() -> None:
    result = runner.invoke(app, ["benchmark", "--help"])
    assert result.exit_code == 0
    assert "--wsi-root" in result.stdout
    assert "--csv-path" in result.stdout
