"""GIANT CLI - Gigapixel Image Agent for Navigating Tissue (Spec-12).

Command-line interface for running GIANT inference and benchmarks.
"""

from __future__ import annotations

import json
import signal
import sys
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer

from giant import __version__
from giant.utils.logging import configure_logging, get_logger

if TYPE_CHECKING:
    pass

app = typer.Typer(
    name="giant",
    help="GIANT: Gigapixel Image Agent for Navigating Tissue",
    add_completion=False,
)


class Mode(str, Enum):
    """Evaluation mode."""

    giant = "giant"  # Full agentic navigation
    thumbnail = "thumbnail"  # Single thumbnail baseline
    patch = "patch"  # Random patch sampling baseline (CLAM)


class Provider(str, Enum):
    """LLM provider."""

    openai = "openai"
    anthropic = "anthropic"


# =============================================================================
# Commands
# =============================================================================


@app.command()
def version(
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Show version information."""
    if json_output:
        typer.echo(json.dumps({"version": __version__}))
    else:
        typer.echo(f"giant {__version__}")


@app.command()
def run(  # noqa: PLR0913
    wsi_path: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Path to WSI file (.svs, .ndpi, .tiff)",
        ),
    ],
    question: Annotated[
        str, typer.Option("--question", "-q", help="Question to answer about the slide")
    ],
    mode: Annotated[Mode, typer.Option("--mode", "-m", help="Evaluation mode")] = Mode.giant,
    provider: Annotated[
        Provider, typer.Option("--provider", "-p", help="LLM provider")
    ] = Provider.anthropic,
    model: Annotated[
        str,
        typer.Option("--model", help="Model name (see docs/models/MODEL_REGISTRY.md)"),
    ] = "claude-sonnet-4-20250514",
    max_steps: Annotated[int, typer.Option("--max-steps", "-T", help="Max navigation steps")] = 20,
    runs: Annotated[int, typer.Option("--runs", "-r", help="Number of runs for majority voting")] = 1,
    budget_usd: Annotated[
        float,
        typer.Option("--budget-usd", help="Stop early if total cost exceeds this USD budget (0 disables)"),
    ] = 0.0,
    output: Annotated[Path | None, typer.Option("--output", "-o", help="Save trajectory to JSON")] = None,
    verbose: Annotated[int, typer.Option("--verbose", "-v", count=True, help="Increase verbosity (-v, -vv, -vvv)")] = 0,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Run GIANT on a single WSI."""
    from giant.cli.runners import run_single_inference

    _configure_logging(verbose)
    logger = get_logger(__name__)

    logger.info(
        "Starting inference",
        wsi=str(wsi_path),
        mode=mode.value,
        provider=provider.value,
    )

    try:
        result = run_single_inference(
            wsi_path=wsi_path,
            question=question,
            mode=mode,
            provider=provider,
            model=model,
            max_steps=max_steps,
            runs=runs,
            budget_usd=budget_usd,
            verbose=verbose,
        )

        # Save trajectory if requested
        if output and hasattr(result, "trajectory") and result.trajectory:
            traj_dict = (
                result.trajectory.to_dict()
                if hasattr(result.trajectory, "to_dict")
                else {"turns": []}
            )
            output.write_text(json.dumps(traj_dict, indent=2))
            logger.info("Trajectory saved", path=str(output))

        # Output results
        if json_output:
            output_data = {
                "success": result.success,
                "answer": result.answer,
                "total_cost": result.total_cost,
                "turns": len(result.trajectory.turns) if result.trajectory else 0,
            }
            typer.echo(json.dumps(output_data, indent=2))
        else:
            typer.echo(f"\nAnswer: {result.answer}")
            typer.echo(f"Cost: ${result.total_cost:.4f}")
            if result.trajectory:
                typer.echo(f"Turns: {len(result.trajectory.turns)}")

        raise typer.Exit(0 if result.success else 1)

    except typer.Exit:
        raise
    except Exception as e:
        logger.exception("Inference failed")
        if json_output:
            typer.echo(json.dumps({"error": str(e)}))
        else:
            typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def benchmark(  # noqa: PLR0913
    dataset: Annotated[
        str,
        typer.Argument(help="Dataset name (tcga, panda, gtex, tcga_expert_vqa, tcga_slidebench)"),
    ],
    csv_path: Annotated[
        Path,
        typer.Option("--csv-path", exists=True, help="Path to MultiPathQA.csv"),
    ] = Path("data/multipathqa/MultiPathQA.csv"),
    wsi_root: Annotated[
        Path,
        typer.Option("--wsi-root", exists=True, help="Root directory containing WSIs"),
    ] = Path("data/wsi"),
    output_dir: Annotated[
        Path, typer.Option("--output-dir", "-o", help="Output directory for results")
    ] = Path("results"),
    mode: Annotated[Mode, typer.Option("--mode", "-m", help="Evaluation mode")] = Mode.giant,
    provider: Annotated[
        Provider, typer.Option("--provider", "-p", help="LLM provider")
    ] = Provider.anthropic,
    model: Annotated[str, typer.Option("--model", help="Model name")] = "claude-sonnet-4-20250514",
    max_steps: Annotated[int, typer.Option("--max-steps", "-T", help="Max navigation steps")] = 20,
    runs: Annotated[int, typer.Option("--runs", "-r", help="Runs per item for majority voting")] = 1,
    concurrency: Annotated[int, typer.Option("--concurrency", "-c", help="Max concurrent API calls")] = 4,
    budget_usd: Annotated[
        float, typer.Option("--budget-usd", help="Stop early if total cost exceeds budget (0 disables)")
    ] = 0.0,
    max_items: Annotated[int, typer.Option("--max-items", help="Max items to evaluate (0 = all)")] = 0,
    skip_missing: Annotated[
        bool, typer.Option("--skip-missing/--no-skip-missing", help="Skip missing WSI files")
    ] = True,
    resume: Annotated[bool, typer.Option("--resume/--no-resume", help="Resume from checkpoint")] = True,
    verbose: Annotated[int, typer.Option("--verbose", "-v", count=True, help="Increase verbosity")] = 0,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Run the full benchmark suite on a dataset."""
    from giant.cli.runners import run_benchmark as run_benchmark_impl

    _configure_logging(verbose)
    logger = get_logger(__name__)

    # Set up signal handlers for graceful shutdown
    shutdown_requested = False

    def signal_handler(signum: int, frame: object) -> None:
        nonlocal shutdown_requested
        if shutdown_requested:
            logger.warning("Force exit requested")
            sys.exit(1)
        shutdown_requested = True
        logger.info("Shutdown requested, finishing current item...")

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info(
        "Starting benchmark",
        dataset=dataset,
        mode=mode.value,
        provider=provider.value,
        concurrency=concurrency,
    )

    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        result = run_benchmark_impl(
            dataset=dataset,
            csv_path=csv_path,
            wsi_root=wsi_root,
            output_dir=output_dir,
            mode=mode,
            provider=provider,
            model=model,
            max_steps=max_steps,
            runs=runs,
            concurrency=concurrency,
            budget_usd=budget_usd,
            resume=resume,
            max_items=max_items,
            skip_missing=skip_missing,
            verbose=verbose,
        )

        if json_output:
            typer.echo(json.dumps(result.metrics, indent=2))
        else:
            typer.echo(f"\nBenchmark: {dataset}")
            typer.echo(f"Mode: {mode.value}")
            typer.echo(f"Results: {result.metrics}")
            typer.echo(f"Total cost: ${result.total_cost:.2f}")

        raise typer.Exit(0)

    except typer.Exit:
        raise
    except Exception as e:
        logger.exception("Benchmark failed")
        if json_output:
            typer.echo(json.dumps({"error": str(e)}))
        else:
            typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def download(
    dataset: Annotated[
        str, typer.Argument(help="Dataset to download (multipathqa, tcga)")
    ] = "multipathqa",
    output_dir: Annotated[
        Path, typer.Option("--output-dir", "-o", help="Output directory")
    ] = Path("data"),
    verbose: Annotated[int, typer.Option("--verbose", "-v", count=True, help="Increase verbosity")] = 0,
) -> None:
    """Download benchmark datasets from HuggingFace."""
    from giant.cli.runners import download_multipathqa

    _configure_logging(verbose)
    logger = get_logger(__name__)

    logger.info("Starting download", dataset=dataset, output_dir=str(output_dir))

    try:
        success = download_multipathqa(
            dataset=dataset,
            output_dir=output_dir,
            verbose=verbose,
        )

        if success:
            typer.echo(f"Downloaded {dataset} to {output_dir}")
            raise typer.Exit(0)
        else:
            typer.echo(f"Download failed for {dataset}", err=True)
            raise typer.Exit(1)

    except typer.Exit:
        raise
    except Exception as e:
        logger.exception("Download failed")
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def visualize(
    trajectory_path: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Path to trajectory JSON file",
        ),
    ],
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Output HTML file path")
    ] = None,
    open_browser: Annotated[
        bool, typer.Option("--open/--no-open", help="Open visualization in browser")
    ] = True,
    verbose: Annotated[int, typer.Option("--verbose", "-v", count=True, help="Increase verbosity")] = 0,
) -> None:
    """Generate interactive visualization of navigation trajectory."""
    from giant.cli.visualizer import create_trajectory_html

    _configure_logging(verbose)
    logger = get_logger(__name__)

    logger.info("Generating visualization", trajectory=str(trajectory_path))

    try:
        html_path = create_trajectory_html(
            trajectory_path=trajectory_path,
            output_path=output,
            open_browser=open_browser,
        )
        typer.echo(f"Visualization saved to {html_path}")
        raise typer.Exit(0)

    except typer.Exit:
        raise
    except Exception as e:
        logger.exception("Visualization failed")
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """GIANT: Gigapixel Image Agent for Navigating Tissue."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


def _configure_logging(verbose: int) -> None:
    """Configure logging based on verbosity level."""
    if verbose == 0:
        level = "WARNING"
    elif verbose == 1:
        level = "INFO"
    elif verbose == 2:
        level = "DEBUG"
    else:
        level = "DEBUG"  # -vvv and beyond

    configure_logging(level=level)


if __name__ == "__main__":  # pragma: no cover
    app()
