"""GIANT CLI - Gigapixel Image Agent for Navigating Tissue.

Command-line interface for running GIANT inference and benchmarks.
Full implementation in Spec-12.
"""

import typer

from giant import __version__

app = typer.Typer(
    name="giant",
    help="GIANT: Gigapixel Image Agent for Navigating Tissue",
    add_completion=False,
)


@app.command()
def version() -> None:
    """Show version information."""
    typer.echo(f"giant {__version__}")


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """GIANT: Gigapixel Image Agent for Navigating Tissue."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


if __name__ == "__main__":
    app()
