# Spec-10: Evaluation & Benchmarking Framework

## Overview
This specification defines the tooling to evaluate GIANT against the MultiPathQA benchmark mentioned in the paper. It includes the logic to load datasets, run the agent in batch mode, calculate metrics (Accuracy, Balanced Accuracy), and compute bootstrap uncertainty estimates. **Paper reporting format:** mean ± standard deviation from 1000 bootstrap replicates (see Table 1).

## Dependencies
- [Spec-09: GIANT Agent Core Loop](./spec-09-giant-agent.md)

## Acceptance Criteria
- [ ] `BenchmarkRunner` class is implemented.
- [ ] Supports loading datasets in JSON/CSV format (compatible with MultiPathQA schema).
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
    id: str
    wsi_path: str
    question: str
    options: List[str]  # For Multiple Choice
    correct_answer: str
    task_type: str # "classification", "vqa", etc.

class BenchmarkResult(BaseModel):
    item_id: str
    prediction: str
    correct: bool
    trajectory_file: str  # Path to saved trajectory JSON
    error: str | None = None
```

### Implementation Details

#### Data Acquisition Module
We use `datasets` and `huggingface_hub` to manage benchmark data.

```python
# src/giant/data/download.py
from huggingface_hub import hf_hub_download, snapshot_download
from datasets import load_dataset
from pathlib import Path
from rich.progress import Progress, SpinnerColumn, TextColumn
from giant.config import settings
import os

# Paper states: "We release the dataset publicly on HuggingFace"
MULTIPATHQA_REPO = "harvard-dbmi/MultiPathQA"  # Verify actual repo name when released

# Dataset structure from paper (Table in Figure 3):
BENCHMARK_TASKS = {
    "tcga": {"questions": 221, "classes": 30, "metric": "balanced_accuracy"},
    "panda": {"questions": 197, "classes": 6, "metric": "balanced_accuracy"},
    "gtex": {"questions": 191, "classes": 20, "metric": "balanced_accuracy"},
    "expertvqa": {"questions": 128, "metric": "accuracy"},
    "slidebenchvqa": {"questions": 197, "metric": "accuracy"},
}

def download_multipathqa(output_dir: Path) -> Path:
    """Download MultiPathQA benchmark from HuggingFace.

    Returns path to downloaded dataset directory.
    """
    os.environ["HF_TOKEN"] = settings.HUGGINGFACE_TOKEN or ""

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}")) as progress:
        task = progress.add_task("Downloading MultiPathQA...", total=None)
        dataset = load_dataset(MULTIPATHQA_REPO, cache_dir=output_dir / "cache")
        progress.update(task, completed=True)

    # Save to local JSON for offline use
    for split in dataset.keys():
        dataset[split].to_json(output_dir / f"{split}.json")

    return output_dir

def download_sample_wsi(output_dir: Path) -> Path:
    """Download sample WSI for testing (small file).

    Uses OpenSlide test data (CMU-1.svs, ~30MB).
    """
    OPENSLIDE_TESTDATA_URL = "https://openslide.cs.cmu.edu/download/openslide-testdata/Aperio/CMU-1.svs"
    import httpx

    output_path = output_dir / "CMU-1.svs"
    if not output_path.exists():
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}")) as progress:
            task = progress.add_task("Downloading sample WSI...", total=None)
            response = httpx.get(OPENSLIDE_TESTDATA_URL, follow_redirects=True)
            output_path.write_bytes(response.content)
            progress.update(task, completed=True)

    return output_path
```

#### Dataset Loader
- Loads from a standard directory structure or a JSON manifest.
- Validates WSI file existence.

#### Batch Execution
- Uses `asyncio` or `ProcessPoolExecutor` (via `pytest-xdist` or similar logic) to run multiple agents in parallel?
  - *Constraint:* WSIs are I/O heavy. OpenSlide + LLM calls.
  - *Recommendation:* Use a semaphore to limit concurrent LLM requests, but run sequential WSI reads if IO bound. Given OpenSlide is fast for reads and LLM is slow, `asyncio` is best.

#### Answer Matching
Comparing model answers to correct answers requires flexible matching:

```python
# src/giant/eval/answer_matcher.py
import re
from typing import Literal

MatchStrategy = Literal["exact", "contains", "option_letter", "fuzzy"]

def match_answer(prediction: str, correct: str, options: list[str] | None = None,
                 strategy: MatchStrategy = "option_letter") -> bool:
    """Match model prediction against correct answer.

    Strategies:
    - exact: Case-insensitive exact match
    - contains: Correct answer substring in prediction
    - option_letter: Extract A/B/C/D from prediction, match to option index
    - fuzzy: Levenshtein distance threshold (for typos)
    """
    prediction = prediction.strip().lower()
    correct = correct.strip().lower()

    if strategy == "exact":
        return prediction == correct
    elif strategy == "contains":
        return correct in prediction
    elif strategy == "option_letter":
        # Extract option letter (A, B, C, D) from prediction
        match = re.search(r'\b([A-D])\b', prediction.upper())
        if match and options:
            letter = match.group(1)
            idx = ord(letter) - ord('A')
            return idx < len(options) and options[idx].lower() == correct
        return False
    elif strategy == "fuzzy":
        from difflib import SequenceMatcher
        return SequenceMatcher(None, prediction, correct).ratio() > 0.8
    return False
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
        std=np.std(scores),
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
├── answer_matcher.py # String matching for answer comparison
└── resumable.py      # Checkpoint/resume logic for interrupted runs

tests/unit/eval/
├── test_metrics.py
├── test_bootstrap.py
└── test_answer_matcher.py

tests/unit/data/
└── test_download.py
```
