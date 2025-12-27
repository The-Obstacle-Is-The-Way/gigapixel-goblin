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
├── gtex_giant_openai_gpt-5.2_summary.json    # Metrics summary
├── checkpoints/
│   └── gtex_giant_openai_gpt-5.2.checkpoint.json  # Resume state
└── trajectories/
    ├── GTEX-OIZH-0626_run0.json              # Per-item trajectories
    └── ...
```

### Results JSON

```json
{
  "run_id": "gtex_giant_openai_gpt-5.2_20251227",
  "dataset": "gtex",
  "provider": "openai",
  "model": "gpt-5.2",
  "items": [
    {
      "image_path": "GTEX-OIZH-0626.tiff",
      "prediction": "Heart",
      "ground_truth": "Heart",
      "correct": true,
      "cost": 0.0378,
      "turns": 3
    },
    ...
  ],
  "metrics": {
    "balanced_accuracy": 0.676,
    "accuracy": 0.712,
    "bootstrap_ci_lower": 0.614,
    "bootstrap_ci_upper": 0.735
  },
  "total_cost": 7.21,
  "n_items": 191,
  "n_errors": 6
}
```

## Metrics

| Metric | Description |
|--------|-------------|
| `accuracy` | Simple accuracy (correct / total) |
| `balanced_accuracy` | Accuracy weighted by class frequency |
| `bootstrap_ci` | 95% confidence interval (1000 replicates) |

Balanced accuracy is the primary metric, matching the paper.

## Cost Estimates

Approximate costs for full benchmark runs:

| Benchmark | Items | Cost (OpenAI) | Time (c=4) |
|-----------|-------|---------------|------------|
| GTEx | 191 | $7-10 | 2-3 hours |
| TCGA | 221 | $8-12 | 2-4 hours |
| PANDA | 197 | $7-10 | 2-3 hours |
| Expert VQA | 128 | $5-8 | 1-2 hours |
| SlideBench | 197 | $7-10 | 2-3 hours |

**Total for all 5 benchmarks:** ~$35-50

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
| GTEx | **67.6%** | 60.7% | 69.1% |
| TCGA | TBD | 32.3% | 40.1% |
| PANDA | TBD | 25.4% | 31.9% |
| Expert VQA | TBD | 62.5% | 71.9% |
| SlideBench | TBD | 58.9% | 68.0% |

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
