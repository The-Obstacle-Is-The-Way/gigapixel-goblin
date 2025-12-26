from giant.cli.main import app


def test_cli_secrets_protection():
    """BUG-035: Verify that locals are hidden in tracebacks."""
    assert app.pretty_exceptions_show_locals is False
