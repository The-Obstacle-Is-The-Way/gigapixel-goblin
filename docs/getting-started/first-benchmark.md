# Your First Benchmark

Run GIANT on the MultiPathQA benchmark to reproduce paper results.

## Prerequisites

- [Installation](installation.md) completed
- API key configured
- WSI files downloaded (see [Data Acquisition](../data/data-acquisition.md))

## Download Benchmark Metadata

```bash
# Download the MultiPathQA CSV (questions, answers, metadata)
giant download multipathqa
```

This creates `data/multipathqa/MultiPathQA.csv` containing 934 questions across 5 benchmarks.

## Check Your Data

Before running benchmarks, verify WSI files are available:

```bash
# Check which files you have
giant check-data gtex
giant check-data tcga
giant check-data panda
```

Example output:
```
All WSIs present for gtex: 191/191 under data/wsi
```

## Run a Subset

Start with a small subset to verify everything works:

```bash
# Run on 5 GTEx items (organ classification)
giant benchmark gtex \
    --provider openai \
    --max-items 5 \
    -v
```

To see machine-readable output (recommended), add `--json`:

```bash
giant benchmark gtex --provider openai --max-items 5 --json | jq
```

## Full Benchmark Run

For complete benchmark runs:

```bash
# Full GTEx (191 items)
giant benchmark gtex --provider openai -v

# TCGA cancer diagnosis (221 items)
giant benchmark tcga --provider openai -v

# With concurrency for faster runs
giant benchmark gtex --concurrency 4 -v

# Resume interrupted runs
giant benchmark gtex --resume -v
```

## Understanding Results

Results are saved to `results/` with:

| File | Contents |
|------|----------|
| `*_results.json` | Full results with predictions |
| `checkpoints/*.checkpoint.json` | Resume state for interrupted runs |
| `trajectories/*.json` | Per-item navigation trajectories |

### Metrics

| Metric | Description |
|--------|-------------|
| `balanced_accuracy` | Accuracy weighted by class frequency |
| `accuracy` | Simple accuracy |
| `bootstrap_ci` | 95% confidence interval |

## Compare to Paper

| Benchmark | Our Result | Paper (GIANT x1) | Paper (GIANT x5) |
|-----------|------------|------------------|------------------|
| GTEx (20-way) | **70.3%** | 53.7% ± 3.4% | 60.7% ± 3.2% |
| ExpertVQA (128 Q) | **60.1%** | 57.0% ± 4.5% | 62.5% ± 4.4% |
| SlideBench (197 Q) | **51.8%** | 58.9% ± 3.5% | 59.4% ± 3.4% |
| TCGA (30-way) | **26.2%** | 32.3% ± 3.5% | 29.3% ± 3.3% |
| PANDA (6-way) | **20.3%** | 23.2% ± 2.3% | 25.4% ± 2.0% |

## Cost Estimates

Costs depend on provider/model, prompt length, and how many steps each item takes. For safe estimation:

1. Run a small sample: `giant benchmark <dataset> --max-items 5 --json`
2. Extrapolate from `total_cost`
3. Use `--budget-usd` as a guardrail on full runs

## Troubleshooting

### "WSI file not found"

```bash
# Check your WSI directory structure
giant check-data gtex -v
```

See [Data Acquisition](../data/data-acquisition.md) for download instructions.

### API Rate Limits

Reduce concurrency:
```bash
giant benchmark gtex --concurrency 1 -v
```

### Resume After Errors

Runs automatically checkpoint. Resume with:
```bash
giant benchmark gtex --resume -v
```

## Next Steps

- [Running Benchmarks Guide](../guides/running-benchmarks.md) - Advanced options
- [Benchmark Results](../results/benchmark-results.md) - Our official results
- [Visualizing Trajectories](../guides/visualizing-trajectories.md) - Inspect agent behavior
