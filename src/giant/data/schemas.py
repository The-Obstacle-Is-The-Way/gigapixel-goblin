"""Data schemas for benchmark evaluation (Spec-10).

Defines the data models for loading and running MultiPathQA benchmarks.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# Dataset structure from GIANT paper (Figure 3 table) and confirmed counts in CSV.
# Key reference: "We release the dataset publicly on HuggingFace" (Section 3)
BENCHMARK_TASKS: dict[str, dict[str, str | int]] = {
    "tcga": {
        "questions": 221,
        "classes": 30,
        "metric": "balanced_accuracy",
        "description": "Cancer diagnosis (30-way classification)",
    },
    "panda": {
        "questions": 197,
        "classes": 6,
        "metric": "balanced_accuracy",
        "description": "Prostate cancer grading (ISUP 0-5)",
    },
    "gtex": {
        "questions": 191,
        "classes": 20,
        "metric": "balanced_accuracy",
        "description": "Organ classification (20-way)",
    },
    "tcga_expert_vqa": {
        "questions": 128,
        "metric": "accuracy",
        "description": "Pathologist-authored VQA questions",
    },
    "tcga_slidebench": {
        "questions": 197,
        "metric": "accuracy",
        "description": "SlideBench VQA questions",
    },
}


class BenchmarkItem(BaseModel):
    """A single benchmark item to evaluate.

    Attributes:
        benchmark_name: Task name (tcga, gtex, panda, tcga_expert_vqa, tcga_slidebench).
        benchmark_id: Row identifier or slide identifier from CSV.
        image_path: Filename from MultiPathQA.csv (resolved under --wsi-root).
        prompt: Question prompt template (may include {options}).
        options: Answer options for multiple-choice (None for open-ended).
        metric_type: "accuracy" or "balanced_accuracy".
        truth_label: Canonicalized label for evaluation (1-based for options).
        wsi_path: Resolved local path to the WSI file.
    """

    benchmark_name: str
    benchmark_id: str
    image_path: str
    prompt: str
    options: list[str] | None = None
    metric_type: str
    truth_label: int
    wsi_path: str


class BenchmarkResult(BaseModel):
    """Result of running the agent on a single benchmark item.

    Attributes:
        item_id: Identifier matching BenchmarkItem.benchmark_id.
        prediction: Raw prediction text from the agent.
        predicted_label: Extracted/canonicalized label (None if extraction failed).
        truth_label: Ground truth label.
        correct: Whether prediction matches truth.
        cost_usd: Total cost in USD for this run.
        total_tokens: Total tokens used for this run.
        trajectory_file: Path to saved trajectory JSON.
        error: Error message if the run failed (None on success).
    """

    item_id: str
    prediction: str
    predicted_label: int | None = None
    truth_label: int
    correct: bool
    cost_usd: float = Field(default=0.0, ge=0.0)
    total_tokens: int = Field(default=0, ge=0)
    trajectory_file: str
    error: str | None = None
