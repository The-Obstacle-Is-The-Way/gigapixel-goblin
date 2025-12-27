# Spec-12: CLI & API Surface

## Overview
This specification defines the user-facing command-line interface (CLI) for GIANT. It uses `Typer` to provide a clean, documented CLI for running single-slide inference, executing benchmarks, downloading data, and visualizing results. The CLI supports all three evaluation modes from the paper: GIANT (agentic), Thumbnail baseline, and Patch baseline.

## Dependencies
- [Spec-09: GIANT Agent Core Loop](./spec-09-giant-agent.md)
- [Spec-10: Evaluation & Benchmarking Framework](./spec-10-evaluation.md)
- [Spec-11: CLAM Integration](./spec-11-clam-integration.md) (for patch baseline)

## Acceptance Criteria
- [x] `giant` command exists and is registered as console script.
- [x] `giant run <path> --question <q>` executes the agent and prints the answer + cost.
- [x] `giant run` supports `--mode {giant,thumbnail,patch}` for baseline comparison.
- [x] `giant run` supports `--runs N` for majority voting (GIANT x5).
- [x] `giant run` supports `--provider {openai,anthropic}` and `--model` selection.
- [x] `giant run` supports `--budget-usd` to cap total spend and fail fast.
- [x] `giant run` supports `--strict-font-check` to fail if axis label fonts are missing.
- [x] `giant benchmark <dataset>` runs the evaluation pipeline with resume support.
- [x] `giant benchmark` supports `--wsi-root <dir>` to resolve `image_path` entries from MultiPathQA metadata to local slide files.
- [x] `giant benchmark` supports `--budget-usd` to cap total spend and fail fast.
- [x] `giant benchmark` supports `--strict-font-check` to fail if axis label fonts are missing.
- [x] `giant benchmark` handles SIGINT/SIGTERM gracefully by writing a final checkpoint before exiting.
- [x] `giant download` downloads MultiPathQA metadata (`MultiPathQA.csv`) from HuggingFace.
- [x] `giant check-data <dataset>` validates that required WSIs exist under `--wsi-root`.
- [x] `giant visualize <result.json>` outputs trajectory visualization.
- [x] Logging verbosity controllable via `-v` / `-vv` / `-vvv` flags.
- [x] `--json` flag outputs machine-readable JSON for all commands.
- [x] Exit codes: 0=success, 1=error, 2=invalid args.

## Technical Design

### CLI Structure (`src/giant/cli/main.py`)

```python
import typer
from typing import Optional
from enum import Enum
from pathlib import Path

app = typer.Typer(
    name="giant",
    help="GIANT: Gigapixel Image Agent for Navigating Tissue",
    add_completion=False,
)

class Mode(str, Enum):
    giant = "giant"       # Full agentic navigation
    thumbnail = "thumbnail"  # Single thumbnail baseline
    patch = "patch"       # Random patch sampling baseline

class Provider(str, Enum):
    openai = "openai"
    anthropic = "anthropic"

@app.command()
def run(
    wsi_path: Path = typer.Argument(..., help="Path to WSI file (.svs, .ndpi, .tiff)"),
    question: str = typer.Option(..., "--question", "-q", help="Question to answer"),
    mode: Mode = typer.Option(Mode.giant, "--mode", "-m", help="Evaluation mode"),
    provider: Provider = typer.Option(Provider.openai, "--provider", "-p"),
    model: str = typer.Option("gpt-5.2", "--model", help="Model name (see docs/models/model-registry.md)"),
    max_steps: int = typer.Option(20, "--max-steps", "-T", help="Max navigation steps"),
    strict_font_check: bool = typer.Option(False, "--strict-font-check/--no-strict-font-check", help="Fail if TrueType fonts are unavailable for axis labels"),
    runs: int = typer.Option(1, "--runs", "-r", help="Number of runs for majority voting"),
    budget_usd: float = typer.Option(0.0, "--budget-usd", help="Stop early if total cost exceeds this USD budget (0 disables)"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Save trajectory to JSON"),
    verbose: int = typer.Option(0, "--verbose", "-v", count=True, help="Increase verbosity"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Run GIANT on a single WSI."""
    ...

@app.command()
def benchmark(
    dataset: str = typer.Argument(..., help="Dataset name or path (tcga, panda, gtex, tcga_expert_vqa|expertvqa, tcga_slidebench|slidebenchvqa)"),
    output_dir: Path = typer.Option(Path("./results"), "--output-dir", "-o"),
    mode: Mode = typer.Option(Mode.giant, "--mode", "-m"),
    provider: Provider = typer.Option(Provider.openai, "--provider", "-p"),
    model: str = typer.Option("gpt-5.2", "--model"),
    max_steps: int = typer.Option(20, "--max-steps", "-T"),
    strict_font_check: bool = typer.Option(False, "--strict-font-check/--no-strict-font-check", help="Fail if TrueType fonts are unavailable for axis labels"),
    runs: int = typer.Option(1, "--runs", "-r", help="Runs per item for majority voting"),
    concurrency: int = typer.Option(4, "--concurrency", "-c", help="Max concurrent API calls"),
    wsi_root: Path = typer.Option(Path("./wsi"), "--wsi-root", help="Root directory containing WSIs referenced by MultiPathQA.csv"),
    budget_usd: float = typer.Option(0.0, "--budget-usd", help="Stop early if total cost exceeds this USD budget (0 disables)"),
    resume: bool = typer.Option(True, "--resume/--no-resume", help="Resume from checkpoint"),
    verbose: int = typer.Option(0, "--verbose", "-v", count=True),
):
    """Run the full benchmark suite."""
    ...

@app.command()
def download(
    dataset: str = typer.Argument("multipathqa", help="Dataset to download"),
    output_dir: Path = typer.Option(Path("./data"), "--output-dir", "-o"),
    verbose: int = typer.Option(0, "--verbose", "-v", count=True),
):
    """Download benchmark datasets from HuggingFace."""
    ...

@app.command()
def check_data(
    dataset: str = typer.Argument(..., help="Dataset name (tcga, panda, gtex, tcga_expert_vqa, tcga_slidebench)"),
    csv_path: Path = typer.Option(Path("data/multipathqa/MultiPathQA.csv"), "--csv-path", help="Path to MultiPathQA.csv"),
    wsi_root: Path = typer.Option(Path("data/wsi"), "--wsi-root", help="Root directory containing WSIs"),
    verbose: int = typer.Option(0, "--verbose", "-v", count=True),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Validate that WSI files for a benchmark exist locally."""
    ...

@app.command()
def visualize(
    trajectory_path: Path = typer.Argument(..., help="Path to trajectory JSON"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output HTML file"),
    open_browser: bool = typer.Option(True, "--open/--no-open", help="Open in browser"),
):
    """Generate interactive visualization of navigation trajectory."""
    ...

@app.command()
def version():
    """Show version information."""
    ...

if __name__ == "__main__":
    app()
```

### pyproject.toml Script Entry
```toml
[project.scripts]
giant = "giant.cli.main:app"
```

### Verbosity Levels
- `-v` (1): INFO logs, show step progress
- `-vv` (2): DEBUG logs, show LLM prompts/responses
- `-vvv` (3): TRACE logs, show all API calls and timing

### Majority Voting (--runs)
When `--runs N` is specified:
1. Run the agent N times independently on the same question
2. Collect all final answers
3. Return the most common answer (majority vote)
4. Report agreement percentage

Paper uses N=5 for "GIANT x5" results.

### Mode Implementation
- **giant**: Full agentic loop (Spec-09)
- **thumbnail**: Single LLM call with 1024x1024 thumbnail
- **patch**: CLAM segmentation + 30 random patches + majority vote (Spec-11)

### Visualization
For `visualize`, generate a static HTML file that:
1. Loads the `trajectory.json`
2. Displays the WSI thumbnail with axis guides
3. Shows each step in a carousel with:
   - The cropped region highlighted on thumbnail
   - The actual crop image
   - The model's reasoning
   - The action taken
4. Final answer summary

### Optional: HTTP Service Mode (Production Deployment)
If GIANT is deployed behind an API (e.g., for a lab internal service), add a separate entrypoint (e.g., `giant serve`) using FastAPI (optional dependency group):
- `GET /healthz` returns 200 if process is alive
- `GET /readyz` validates required config (API keys, model selection) and can do a lightweight provider auth check (no image)
- Graceful shutdown on SIGTERM/SIGINT: stop accepting new requests, persist in-flight trajectory/checkpoint, and close OpenSlide handles

## Test Plan

### Unit Tests
1. **CLI Parsing:** Test all argument combinations parse correctly.
2. **Mode Selection:** Verify correct runner is instantiated for each mode.
3. **Verbosity:** Test log level is set correctly for -v, -vv, -vvv.
4. **JSON Output:** Verify --json produces valid JSON.
5. **Exit Codes:** Test exit code 0 on success, 1 on error.

### Integration Tests
1. **Run Command:** Mock LLM, verify end-to-end flow.
2. **Benchmark Resume:** Start benchmark, interrupt, resume, verify no duplicates.
3. **Download Command:** Mock HuggingFace, verify files created.

## File Structure
```text
src/giant/cli/
├── __init__.py
├── main.py         # Typer app with all commands
├── runners.py      # Mode-specific runner wrappers
├── visualizer.py   # HTML generation for trajectories

tests/unit/cli/
├── test_main.py
├── test_runners.py
└── test_visualizer.py

tests/integration/cli/
└── test_cli_e2e.py
```
