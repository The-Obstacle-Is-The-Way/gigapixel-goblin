"""GIANT CLI - Gigapixel Image Agent for Navigating Tissue.

Command-line interface for running GIANT inference and benchmarks.
Full implementation in Spec-12.
"""

from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path

import typer

from giant import __version__
from giant.utils.logging import configure_logging, get_logger

app = typer.Typer(
    name="giant",
    help="GIANT: Gigapixel Image Agent for Navigating Tissue",
    add_completion=False,
)

DATASET_DIR_ARG = typer.Argument(
    ...,
    exists=True,
    file_okay=False,
    dir_okay=True,
    readable=True,
    help="Path to the MultiPathQA dataset directory (expects MultiPathQA.csv).",
)

OUTPUT_DIR_OPT = typer.Option(
    Path("results"),
    "--output-dir",
    "-o",
    file_okay=False,
    dir_okay=True,
    writable=True,
    help="Directory to write benchmark outputs.",
)


@app.command()
def version() -> None:
    """Show version information."""
    typer.echo(f"giant {__version__}")


@app.command()
def benchmark(
    dataset_dir: Path = DATASET_DIR_ARG,
    output_dir: Path = OUTPUT_DIR_OPT,
) -> None:
    """Run a fast benchmark smoke test.

    This command exists to support the Spec-01 toolchain end-to-end. The full,
    paper-faithful benchmark pipeline is implemented in Spec-10 and wired in
    Spec-12.
    """
    configure_logging()
    logger = get_logger(__name__)

    csv_path = dataset_dir / "MultiPathQA.csv"
    if not csv_path.exists():
        raise typer.BadParameter(
            f"Expected metadata CSV at {csv_path}. Run `make download-data` first."
        )

    total_rows = 0
    benchmark_counts: dict[str, int] = {}

    with csv_path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            total_rows += 1
            name = (row.get("benchmark_name") or "").strip()
            benchmark_counts[name] = benchmark_counts.get(name, 0) + 1

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "benchmark_smoke.json"
    payload = {
        "smoke": True,
        "giant_version": __version__,
        "timestamp": datetime.now(UTC).isoformat(),
        "dataset_dir": str(dataset_dir),
        "csv_path": str(csv_path),
        "total_rows": total_rows,
        "by_benchmark": dict(sorted(benchmark_counts.items())),
    }
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    logger.info(
        "Benchmark smoke test complete",
        total_rows=total_rows,
        output=str(out_path),
    )
    typer.echo(str(out_path))


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """GIANT: Gigapixel Image Agent for Navigating Tissue."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


if __name__ == "__main__":  # pragma: no cover
    app()
