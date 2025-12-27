# Running Benchmarks

This guide covers running GIANT on the MultiPathQA benchmark suite.

## Prerequisites

1. [Installation](../getting-started/installation.md) completed
2. API key configured in `.env`
3. WSI files downloaded (see [Data Acquisition](../data-acquisition.md))
4. MultiPathQA metadata downloaded:
   ```bash
   giant download multipathqa
   ```

## Basic Usage

```bash
giant benchmark <dataset> [options]
```

### Available Datasets

| Dataset | Task | Items | WSI Source |
|---------|------|-------|------------|
| `gtex` | Organ Classification (20-way) | 191 | GTEx |
| `tcga` | Cancer Diagnosis (30-way) | 221 | TCGA |
| `panda` | Prostate Grading (6-way) | 197 | PANDA |
| `tcga_expert_vqa` | Pathologist-Authored VQA | 128 | TCGA |
| `tcga_slidebench` | SlideBench VQA | 197 | TCGA |

### Example

```bash
# Full GTEx benchmark
giant benchmark gtex --provider openai -v
```

## Command Options

### Data Options

| Option | Default | Description |
|--------|---------|-------------|
| `--csv-path` | `data/multipathqa/MultiPathQA.csv` | Path to benchmark CSV |
| `--wsi-root` | `data/wsi` | Root directory for WSI files |
| `-o, --output-dir` | `results` | Output directory |

### Provider Options

| Option | Default | Description |
|--------|---------|-------------|
| `-p, --provider` | `openai` | LLM provider |
| `--model` | `gpt-5.2` | Model ID |

### Run Options

| Option | Default | Description |
|--------|---------|-------------|
| `-T, --max-steps` | `20` | Max navigation steps per item |
| `-r, --runs` | `1` | Runs per item (for majority voting) |
| `-c, --concurrency` | `4` | Max concurrent API calls |
| `--max-items` | `0` (all) | Limit items to process |
| `--budget-usd` | `0` (disabled) | Total cost budget |
| `--skip-missing/--no-skip-missing` | `--skip-missing` | Skip missing WSI files |
| `--resume/--no-resume` | `--resume` | Resume from checkpoint |

### Output Options

| Option | Default | Description |
|--------|---------|-------------|
| `--json` | False | JSON output for scripting |
| `-v, --verbose` | 0 | Verbosity level |

## Workflow Examples

### Quick Validation (5 items)

```bash
giant benchmark gtex \
    --max-items 5 \
    --provider openai \
    -v
```

### Full Benchmark with Resume

```bash
# Start benchmark (may take hours)
giant benchmark tcga --provider openai -v

# If interrupted, resume:
giant benchmark tcga --resume -v
```

### High Concurrency

```bash
# Faster but higher API load
giant benchmark gtex --concurrency 8 -v
```

### Multiple Runs (Majority Voting)

```bash
# 3 runs per item, report majority vote
giant benchmark gtex --runs 3 -v
```

### Cost-Limited Run

```bash
# Stop when budget is exhausted
giant benchmark tcga --budget-usd 10.00 -v
```

## Output Structure

Results are saved to `--output-dir` (default: `results/`):

```
results/
├── gtex_giant_openai_gpt-5.2_results.json    # Full results
├── checkpoints/
│   └── gtex_giant_openai_gpt-5.2.checkpoint.json  # Resume state
└── trajectories/
    ├── GTEX-OIZH-0626_run0.json              # Per-item trajectories
    └── ...
```

### Results JSON

```json
{
  "run_id": "gtex_giant_openai_gpt-5.2",
  "benchmark_name": "gtex",
  "model_name": "gpt-5.2",
  "config": {
    "mode": "giant",
    "max_steps": 20,
    "runs_per_item": 1,
    "max_concurrent": 4,
    "max_items": null,
    "skip_missing_wsis": true
  },
  "results": [
    {
      "item_id": "GTEX-OIZH-0626",
      "prediction": "Heart",
      "predicted_label": 1,
      "truth_label": 1,
      "correct": true,
      "cost_usd": 0.0378,
      "total_tokens": 1234,
      "trajectory_file": "results/trajectories/GTEX-OIZH-0626_run0.json",
      "error": null
    },
    ...
  ],
  "metrics": {
    "metric_type": "balanced_accuracy",
    "bootstrap_mean": 0.676,
    "bootstrap_std": 0.031,
    "bootstrap_ci_lower": 0.614,
    "bootstrap_ci_upper": 0.735,
    "n_replicates": 1000
  },
  "total_cost_usd": 7.21,
  "total_tokens": 1234567,
  "timestamp": "2025-12-27T00:00:00Z"
}
```

## Metrics

| Metric | Description |
|--------|-------------|
| `metric_type` | `"balanced_accuracy"` for classification, `"accuracy"` for VQA |
| `bootstrap_mean` | Bootstrap mean of the metric |
| `bootstrap_std` | Bootstrap standard deviation |
| `bootstrap_ci_lower` / `bootstrap_ci_upper` | 95% bootstrap confidence interval |

Classification tasks (`tcga`, `gtex`, `panda`) use balanced accuracy (per the paper). VQA tasks use accuracy.

## Cost Estimates

Costs vary significantly by provider/model and how many steps the agent uses per item. For a safe estimate:

1. Run a small sample: `giant benchmark <dataset> --max-items 5 --json`
2. Extrapolate from `total_cost`
3. Use `--budget-usd` on longer runs

## Checkpoint and Resume

Benchmarks automatically checkpoint progress:

1. After each item completes
2. On graceful shutdown (Ctrl+C)

To resume an interrupted run:

```bash
giant benchmark gtex --resume -v
```

The checkpoint file contains:
- Completed item indices
- Partial results
- Run configuration

## Handling Missing Files

By default, missing WSI files are skipped:

```bash
# Skip missing (default)
giant benchmark gtex --skip-missing -v

# Fail on missing
giant benchmark gtex --no-skip-missing -v
```

Check which files are missing:

```bash
giant check-data gtex -v
```

## Comparing to Paper Results

| Benchmark | Our Result | Paper (GIANT x1) | Paper (GIANT x5) |
|-----------|------------|------------------|------------------|
| GTEx | **67.6%** | 53.7% | 60.7% |
| TCGA | TBD | 32.3% | 29.3% |
| PANDA | TBD | 23.2% | 25.4% |
| Expert VQA | TBD | 57.0% | 62.5% |
| SlideBench | TBD | 58.9% | 59.4% |

See [Benchmark Results](../results/benchmark-results.md) for detailed analysis.

## Troubleshooting

### "WSI file not found"

Check data availability:
```bash
giant check-data gtex -v
```

See [Data Acquisition](../data-acquisition.md) for download instructions.

### Rate Limits

Reduce concurrency:
```bash
giant benchmark gtex --concurrency 1 -v
```

### Memory Issues

Large WSIs can consume memory. Try:
```bash
# Process one at a time
giant benchmark gtex --concurrency 1 -v
```

### Checkpoint Corruption

Delete the checkpoint and restart:
```bash
rm results/checkpoints/gtex_*.checkpoint.json
giant benchmark gtex -v
```

## Next Steps

- [Visualizing Trajectories](visualizing-trajectories.md) - Inspect results
- [Benchmark Results](../results/benchmark-results.md) - Official results
- [CLI Reference](../reference/cli.md) - All options
