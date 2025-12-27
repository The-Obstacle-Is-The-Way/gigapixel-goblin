from typer.testing import CliRunner

from giant.cli.main import app

runner = CliRunner()


def test_cli_secrets_protection_attribute():
    """BUG-035: Verify that pretty_exceptions_show_locals is disabled."""
    assert app.pretty_exceptions_show_locals is False


def test_cli_secrets_not_in_error_output(monkeypatch):
    """BUG-035: Verify secrets don't appear in CLI error output.

    Sets a fake API key and triggers an error, then verifies the secret
    doesn't appear in stdout/stderr.
    """
    secret = "sk-ant-TESTSECRET123456789"
    monkeypatch.setenv("ANTHROPIC_API_KEY", secret)

    # Trigger an error by running a command with invalid arguments
    # Using 'run' with a non-existent file should error
    result = runner.invoke(app, ["run", "/nonexistent/path.svs", "-q", "test"])

    # The command should fail (non-zero exit code)
    assert result.exit_code != 0

    # The secret should NOT appear in output
    assert secret not in result.stdout
    assert secret not in (result.stderr or "")
    # Also check the full output including any exception text
    assert secret not in str(result.output)
