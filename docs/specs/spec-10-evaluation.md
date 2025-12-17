# Spec-10: Evaluation & Benchmarking Framework

## Overview
This specification defines the tooling to evaluate GIANT against the MultiPathQA benchmark used in the paper. It includes the logic to load benchmark items, run the agent in batch mode, calculate metrics (Accuracy, Balanced Accuracy), and compute bootstrap uncertainty estimates. **Paper reporting format:** mean ± standard deviation from 1000 bootstrap replicates (see Table 1).

**First-principles note (HuggingFace release):** As of 2025-11-26, MultiPathQA is available as a single CSV at `tbuckley/MultiPathQA` (`MultiPathQA.csv`). The CSV contains question/prompt metadata and slide IDs/filenames; WSIs themselves may need to be acquired separately and placed under a user-provided `--wsi-root`.

## Dependencies
- [Spec-09: GIANT Agent Core Loop](./spec-09-giant-agent.md)

## Acceptance Criteria
- [ ] `BenchmarkRunner` class is implemented.
- [ ] Supports loading MultiPathQA metadata from `MultiPathQA.csv` (HuggingFace) and/or a local CSV/JSON export.
- [ ] Requires a `wsi_root` input and resolves each `image_path` to a local WSI file (clear error if missing).
- [ ] Implements dataset-aware answer extraction (1-based option indices, PANDA JSON `isup_grade`, GTEx label→index mapping).
- [ ] Supports `runs_per_item >= 1` with majority voting (paper’s GIANT×5 is `runs_per_item=5`).
- [ ] `MetricsCalculator` computes Accuracy and Balanced Accuracy.
- [ ] `BootstrapEvaluator` computes **mean ± std dev** using 1000 bootstrap replicates (paper reporting format).
- [ ] (Optional) `BootstrapEvaluator` can also compute 95% percentile intervals for internal analysis.
- [ ] Results are saved to a structured JSON file with full provenance.
- [ ] Supports resuming interrupted runs.

## Technical Design

### Data Models

```python
from pydantic import BaseModel
from typing import List, Dict, Any

class BenchmarkItem(BaseModel):
    benchmark_name: str   # e.g., tcga, gtex, panda, tcga_expert_vqa, tcga_slidebench
    benchmark_id: str     # row identifier / slide identifier
    image_path: str       # filename from MultiPathQA.csv (resolved under --wsi-root)
    prompt: str           # question prompt template from CSV (may include {options})
    options: List[str] | None = None
    metric_type: str      # "accuracy" or "balanced_accuracy" (from CSV)
    truth_label: int      # canonicalized label for evaluation (see Answer Extraction)
    wsi_path: str         # resolved local path to WSI

class BenchmarkResult(BaseModel):
    item_id: str
    prediction: str
    predicted_label: int | None = None
    truth_label: int
    correct: bool
    cost_usd: float = 0.0
    total_tokens: int = 0
    trajectory_file: str  # Path to saved trajectory JSON
    error: str | None = None
```

### Implementation Details

#### Data Acquisition Module
We use `datasets` and `huggingface_hub` to manage benchmark data.

```python
# src/giant/data/download.py
from huggingface_hub import hf_hub_download
from pathlib import Path
from rich.progress import Progress, SpinnerColumn, TextColumn
from giant.config import settings
import os

# Paper states: "We release the dataset publicly on HuggingFace"
MULTIPATHQA_REPO = "tbuckley/MultiPathQA"  # Verified via HuggingFace API (2025-11-26)
MULTIPATHQA_FILENAME = "MultiPathQA.csv"

# Dataset structure from paper (Figure 3 table) and confirmed counts in the CSV:
BENCHMARK_TASKS = {
    "tcga": {"questions": 221, "classes": 30, "metric": "balanced_accuracy"},
    "panda": {"questions": 197, "classes": 6, "metric": "balanced_accuracy"},
    "gtex": {"questions": 191, "classes": 20, "metric": "balanced_accuracy"},
    "tcga_expert_vqa": {"questions": 128, "metric": "accuracy"},
    "tcga_slidebench": {"questions": 197, "metric": "accuracy"},
}

def download_multipathqa(output_dir: Path) -> Path:
    """Download MultiPathQA CSV metadata from HuggingFace.

    NOTE: This downloads the question metadata CSV, not the WSIs themselves.
    """
    os.environ["HF_TOKEN"] = settings.HUGGINGFACE_TOKEN or ""
    output_dir.mkdir(parents=True, exist_ok=True)

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}")) as progress:
        task = progress.add_task("Downloading MultiPathQA.csv...", total=None)
        csv_path = hf_hub_download(
            repo_id=MULTIPATHQA_REPO,
            repo_type="dataset",
            filename=MULTIPATHQA_FILENAME,
            local_dir=output_dir,
            local_dir_use_symlinks=False,
        )
        progress.update(task, completed=True)

    return Path(csv_path)

def download_sample_wsi(output_dir: Path) -> Path:
    """Download sample WSI for testing (small file).

    Uses OpenSlide test data (CMU-1.svs, ~30MB).
    """
    OPENSLIDE_TESTDATA_URL = "https://openslide.cs.cmu.edu/download/openslide-testdata/Aperio/CMU-1.svs"
    import httpx

    output_path = output_dir / "CMU-1.svs"
    if not output_path.exists():
        # Production-readiness: check available disk space before downloading large assets.
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}")) as progress:
            task = progress.add_task("Downloading sample WSI...", total=None)
            response = httpx.get(OPENSLIDE_TESTDATA_URL, follow_redirects=True)
            output_path.write_bytes(response.content)
            progress.update(task, completed=True)

    return output_path
```

#### Dataset Loader
- Loads from a standard directory structure or a JSON manifest.
- Loads `MultiPathQA.csv` and filters `is_valid == True`.
- Resolves `image_path` to a local WSI path under a required `wsi_root` directory.
  - Resolution strategy (robust): try `wsi_root / image_path`, then `wsi_root / benchmark_name / image_path`, then fail with a clear error.
- Parses `options` from the CSV (when present) and substitutes `{options}` into `prompt` before sending to the agent.
- Canonicalizes `truth_label`:
  - If CSV `answer` is an integer string: `truth_label = int(answer)` (MultiPathQA uses 1-based indices for options tasks).
  - If CSV `answer` is a string label (GTEx): `truth_label = options.index(answer) + 1`.

#### WSI Acquisition & Local Layout (Operational Requirement)
MultiPathQA CSV rows reference slide filenames in `image_path`:
- TCGA-derived benchmarks use `.svs`
- GTEx and PANDA use `.tiff`

Because WSIs may not be redistributed via HuggingFace, evaluation requires the operator to populate `--wsi-root` with the referenced files.

**Recommended layout:**
```text
wsi_root/
├── gtex/*.tiff
├── panda/*.tiff
└── tcga/*.svs
```

The loader should also work if all files are placed directly under `wsi_root/`.

#### Batch Execution
- Use `asyncio` for concurrent LLM calls with a bounded semaphore.
- Use provider-level rate limiting (`aiolimiter`, Spec-06) to stay within RPM limits.
- Keep OpenSlide reads inside the agent and avoid reading full slides; use thread offload only if profiling shows blocking impacts throughput.

#### Answer Extraction & Matching (MultiPathQA CSV-Faithful)
MultiPathQA truth labels are heterogeneous:
- `tcga`, `tcga_expert_vqa`, `tcga_slidebench`: `answer` is a **1-based option index** in the CSV.
- `panda`: `answer` is the ISUP grade `0..5`; prompt expects a JSON object containing `"isup_grade"`.
- `gtex`: `answer` is a **string label**; options list contains the 20 organ names.

Implement dataset-aware extraction to canonicalize predictions into an `int` label for metrics.

```python
# src/giant/eval/answer_extraction.py
import json
import re
from dataclasses import dataclass

_INT_RE = re.compile(r"\b(\d+)\b")
_LETTER_RE = re.compile(r"\b([A-D])\b", re.IGNORECASE)

@dataclass(frozen=True)
class ExtractedAnswer:
    label: int | None
    raw: str

def extract_label(prediction: str, *, benchmark_name: str, options: list[str] | None) -> ExtractedAnswer:
    \"\"\"Return a canonical integer label for scoring.

    Conventions:
    - Multiple-choice tasks use 1-based labels (matches MultiPathQA CSV).
    - PANDA uses isup_grade 0..5.
    \"\"\"
    text = prediction.strip()

    if benchmark_name == "panda":
        # Extract JSON object and read isup_grade
        try:
            obj = json.loads(_extract_json_object(text))
            grade = int(obj["isup_grade"])
            return ExtractedAnswer(label=grade, raw=text)
        except Exception:
            # fall through to integer extraction
            pass

    # If options exist, accept letter (A-D), 1..N integer, or option text match.
    if options:
        m = _LETTER_RE.search(text)
        if m and len(options) == 4:
            return ExtractedAnswer(label=(ord(m.group(1).upper()) - ord("A") + 1), raw=text)

        m = _INT_RE.search(text)
        if m:
            k = int(m.group(1))
            if 1 <= k <= len(options):
                return ExtractedAnswer(label=k, raw=text)

        lowered = text.lower()
        for i, opt in enumerate(options, start=1):
            if opt.lower() in lowered:
                return ExtractedAnswer(label=i, raw=text)

    # No options: try integer extraction (e.g., PANDA grade)
    m = _INT_RE.search(text)
    return ExtractedAnswer(label=(int(m.group(1)) if m else None), raw=text)


def _extract_json_object(text: str) -> str:
    # Naive but practical: find outermost {...}
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found")
    return text[start : end + 1]
```

#### Bootstrapping (Paper-Faithful)

**Paper Reference:** Table 1 reports metrics as "value ± std" from 1000 bootstrap replicates.

**Algorithm:**
1.  Input: List of `(prediction, truth)` pairs of length N.
2.  Repeat `B=1000` times:
    - Sample N pairs **with replacement**.
    - Calculate the metric (Accuracy or Balanced Accuracy).
3.  **Primary output (paper format):** Report bootstrap **mean** and **standard deviation**.
4.  **Optional output:** Also compute 2.5th / 97.5th percentiles for 95% bootstrap interval.

```python
import numpy as np
from dataclasses import dataclass

@dataclass
class BootstrapResult:
    mean: float
    std: float
    ci_lower: float  # 2.5th percentile
    ci_upper: float  # 97.5th percentile
    n_replicates: int = 1000

def bootstrap_metric(
    predictions: list[str],
    truths: list[str],
    metric_fn: Callable[[list[str], list[str]], float],
    n_replicates: int = 1000,
    seed: int = 42,
) -> BootstrapResult:
    rng = np.random.default_rng(seed)
    n = len(predictions)
    scores = []
    for _ in range(n_replicates):
        idx = rng.choice(n, size=n, replace=True)
        sample_pred = [predictions[i] for i in idx]
        sample_truth = [truths[i] for i in idx]
        scores.append(metric_fn(sample_pred, sample_truth))
    return BootstrapResult(
        mean=np.mean(scores),
        std=np.std(scores, ddof=1),
        ci_lower=np.percentile(scores, 2.5),
        ci_upper=np.percentile(scores, 97.5),
        n_replicates=n_replicates,
    )
```

## Test Plan

### Unit Tests
1.  **Metrics:** Test Balanced Accuracy with imbalanced inputs.
2.  **Bootstrap:** Test logic on a small known set of numbers.

## File Structure
```text
src/giant/data/
├── __init__.py
├── download.py       # HuggingFace download utilities
└── schemas.py        # BenchmarkItem, dataset task definitions

src/giant/eval/
├── __init__.py
├── runner.py         # Batch execution (BenchmarkRunner)
├── metrics.py        # Accuracy, Balanced Accuracy, BootstrapEvaluator
├── answer_extraction.py # Dataset-aware answer extraction/canonicalization
└── resumable.py      # Checkpoint/resume logic for interrupted runs

tests/unit/eval/
├── test_metrics.py
├── test_bootstrap.py
└── test_answer_extraction.py

tests/unit/data/
└── test_download.py
```
