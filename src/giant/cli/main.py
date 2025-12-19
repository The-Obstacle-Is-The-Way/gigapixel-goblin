"""GIANT CLI - Gigapixel Image Agent for Navigating Tissue (Spec-12).

Command-line interface for running GIANT inference and benchmarks.
"""

from __future__ import annotations

import json
import signal
from enum import Enum
from pathlib import Path
from typing import Annotated

import typer

from giant import __version__
from giant.utils.logging import configure_logging, get_logger

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
    mode: Annotated[
        Mode, typer.Option("--mode", "-m", help="Evaluation mode")
    ] = Mode.giant,
    provider: Annotated[
        Provider, typer.Option("--provider", "-p", help="LLM provider")
    ] = Provider.openai,
    model: Annotated[
        str,
        typer.Option("--model", help="Model name (see docs/models/MODEL_REGISTRY.md)"),
    ] = "gpt-5.2",
    max_steps: Annotated[
        int, typer.Option("--max-steps", "-T", help="Max navigation steps")
    ] = 20,
    runs: Annotated[
        int, typer.Option("--runs", "-r", help="Number of runs for majority voting")
    ] = 1,
    budget_usd: Annotated[
        float,
        typer.Option(
            "--budget-usd",
            help="Stop early if total cost exceeds this USD budget (0 disables)",
        ),
    ] = 0.0,
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Save trajectory to JSON")
    ] = None,
    verbose: Annotated[
        int,
        typer.Option(
            "--verbose", "-v", count=True, help="Increase verbosity (-v, -vv, -vvv)"
        ),
    ] = 0,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Run GIANT on a single WSI."""
    from giant.cli.runners import run_single_inference  # noqa: PLC0415

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

        turns_count = _trajectory_turn_count(result.trajectory)

        # Save run artifact (trajectory + metadata) if requested.
        if output is not None:
            trajectory_dict = _trajectory_to_dict(result.trajectory)
            artifact = {
                **trajectory_dict,
                "answer": result.answer,
                "success": result.success,
                "total_cost": result.total_cost,
                "mode": mode.value,
                "provider": provider.value,
                "model": model,
                "runs": runs,
                "agreement": result.agreement,
                "runs_answers": result.runs_answers,
            }
            output.write_text(json.dumps(artifact, indent=2))
            logger.info("Run artifact saved", path=str(output))

        # Output results
        if json_output:
            output_data = {
                "success": result.success,
                "answer": result.answer,
                "total_cost": result.total_cost,
                "agreement": result.agreement,
                "turns": turns_count,
            }
            typer.echo(json.dumps(output_data, indent=2))
        else:
            typer.echo(f"\nAnswer: {result.answer}")
            typer.echo(f"Cost: ${result.total_cost:.4f}")
            if runs > 1:
                typer.echo(f"Agreement: {result.agreement:.0%}")
            if turns_count:
                typer.echo(f"Turns: {turns_count}")

        raise typer.Exit(0 if result.success else 1)

    except typer.Exit:
        raise
    except Exception as e:
        logger.exception("Inference failed")
        if json_output:
            typer.echo(json.dumps({"error": str(e)}))
        else:
            typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1) from None


@app.command()
def benchmark(  # noqa: PLR0913
    dataset: Annotated[
        str,
        typer.Argument(
            help="Dataset name (tcga, panda, gtex, tcga_expert_vqa, tcga_slidebench)"
        ),
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
    mode: Annotated[
        Mode, typer.Option("--mode", "-m", help="Evaluation mode")
    ] = Mode.giant,
    provider: Annotated[
        Provider, typer.Option("--provider", "-p", help="LLM provider")
    ] = Provider.openai,
    model: Annotated[str, typer.Option("--model", help="Model name")] = "gpt-5.2",
    max_steps: Annotated[
        int, typer.Option("--max-steps", "-T", help="Max navigation steps")
    ] = 20,
    runs: Annotated[
        int, typer.Option("--runs", "-r", help="Runs per item for majority voting")
    ] = 1,
    concurrency: Annotated[
        int, typer.Option("--concurrency", "-c", help="Max concurrent API calls")
    ] = 4,
    budget_usd: Annotated[
        float,
        typer.Option(
            "--budget-usd", help="Stop early if total cost exceeds budget (0 disables)"
        ),
    ] = 0.0,
    max_items: Annotated[
        int, typer.Option("--max-items", help="Max items to evaluate (0 = all)")
    ] = 0,
    skip_missing: Annotated[
        bool,
        typer.Option("--skip-missing/--no-skip-missing", help="Skip missing WSI files"),
    ] = True,
    resume: Annotated[
        bool, typer.Option("--resume/--no-resume", help="Resume from checkpoint")
    ] = True,
    verbose: Annotated[
        int, typer.Option("--verbose", "-v", count=True, help="Increase verbosity")
    ] = 0,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Run the full benchmark suite on a dataset."""
    from giant.cli.runners import run_benchmark as run_benchmark_impl  # noqa: PLC0415

    _configure_logging(verbose)
    logger = get_logger(__name__)

    # Set up signal handlers for graceful shutdown (translate SIGTERM into a
    # KeyboardInterrupt so asyncio cancellation paths can checkpoint).
    def signal_handler(signum: int, frame: object) -> None:
        logger.warning("Shutdown requested", signal=signum)
        raise KeyboardInterrupt()

    original_sigint = signal.getsignal(signal.SIGINT)
    original_sigterm = signal.getsignal(signal.SIGTERM)
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
            typer.echo(
                json.dumps(
                    {
                        "dataset": dataset,
                        "mode": mode.value,
                        "provider": provider.value,
                        "model": model,
                        "metrics": result.metrics,
                        "total_cost": result.total_cost,
                        "n_items": result.n_items,
                        "n_errors": result.n_errors,
                        "run_id": result.run_id,
                        "results_path": str(result.results_path),
                    },
                    indent=2,
                )
            )
        else:
            typer.echo(f"\nBenchmark: {dataset}")
            typer.echo(f"Mode: {mode.value}")
            typer.echo(f"Results: {result.metrics}")
            typer.echo(f"Total cost: ${result.total_cost:.2f}")
            typer.echo(f"Run ID: {result.run_id}")
            typer.echo(f"Results file: {result.results_path}")

        raise typer.Exit(0)

    except KeyboardInterrupt:
        logger.warning("Benchmark interrupted (checkpoint saved if possible)")
        raise typer.Exit(1) from None
    except typer.Exit:
        raise
    except Exception as e:
        logger.exception("Benchmark failed")
        if json_output:
            typer.echo(json.dumps({"error": str(e)}))
        else:
            typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1) from None
    finally:
        signal.signal(signal.SIGINT, original_sigint)
        signal.signal(signal.SIGTERM, original_sigterm)


@app.command()
def download(
    dataset: Annotated[
        str, typer.Argument(help="Dataset to download (multipathqa)")
    ] = "multipathqa",
    output_dir: Annotated[
        Path, typer.Option("--output-dir", "-o", help="Output directory")
    ] = Path("data"),
    force: Annotated[
        bool, typer.Option("--force", help="Re-download even if file exists")
    ] = False,
    verbose: Annotated[
        int, typer.Option("--verbose", "-v", count=True, help="Increase verbosity")
    ] = 0,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Download benchmark datasets from HuggingFace."""
    from giant.cli.runners import download_dataset  # noqa: PLC0415

    _configure_logging(verbose)
    logger = get_logger(__name__)

    logger.info("Starting download", dataset=dataset, output_dir=str(output_dir))

    try:
        result = download_dataset(
            dataset=dataset,
            output_dir=output_dir,
            force=force,
            verbose=verbose,
        )

        if json_output:
            typer.echo(json.dumps(result, indent=2))
        else:
            typer.echo(f"Downloaded {dataset} to {result['path']}")

        raise typer.Exit(0)

    except typer.Exit:
        raise
    except Exception as e:
        logger.exception("Download failed")
        if json_output:
            typer.echo(json.dumps({"error": str(e)}))
        else:
            typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1) from None


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
    verbose: Annotated[
        int, typer.Option("--verbose", "-v", count=True, help="Increase verbosity")
    ] = 0,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Generate interactive visualization of navigation trajectory."""
    from giant.cli.visualizer import create_trajectory_html  # noqa: PLC0415

    _configure_logging(verbose)
    logger = get_logger(__name__)

    logger.info("Generating visualization", trajectory=str(trajectory_path))

    try:
        html_path = create_trajectory_html(
            trajectory_path=trajectory_path,
            output_path=output,
            open_browser=open_browser,
        )
        if json_output:
            typer.echo(json.dumps({"html_path": str(html_path)}))
        else:
            typer.echo(f"Visualization saved to {html_path}")
        raise typer.Exit(0)

    except typer.Exit:
        raise
    except Exception as e:
        logger.exception("Visualization failed")
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1) from None


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
    else:  # verbose >= 2
        level = "DEBUG"

    configure_logging(level=level)


def _trajectory_to_dict(trajectory: object | None) -> dict[str, object]:
    if trajectory is None:
        return {}
    if isinstance(trajectory, dict):
        return dict(trajectory)

    model_dump = getattr(trajectory, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        if isinstance(dumped, dict):
            return dumped
    return {}


def _trajectory_turn_count(trajectory: object | None) -> int:
    turns = getattr(trajectory, "turns", None)
    return len(turns) if isinstance(turns, list) else 0


if __name__ == "__main__":  # pragma: no cover
    app()
