# Your First Benchmark

Run GIANT on the MultiPathQA benchmark to reproduce paper results.

## Prerequisites

- [Installation](installation.md) completed
- API key configured
- WSI files downloaded (see [Data Acquisition](../data-acquisition.md))

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
gtex: 191/191 files found (100.0%)
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

Expected output:
```
Benchmark: gtex
Mode: giant
Results: {'balanced_accuracy': 0.80, 'accuracy': 0.80}
Total cost: $0.18
Run ID: gtex_giant_openai_gpt-5.2_20251227
Results file: results/gtex_giant_openai_gpt-5.2_results.json
```

## Full Benchmark Run

For complete benchmark runs:

```bash
# Full GTEx (191 items, ~$7 cost, ~2 hours)
giant benchmark gtex --provider openai -v

# TCGA cancer diagnosis (221 items, ~$10 cost, ~3 hours)
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
| GTEx (20-way) | 67.6% | 60.7% | 69.1% |
| TCGA (30-way) | TBD | 32.3% | 40.1% |
| PANDA (6-way) | TBD | 25.4% | 31.9% |

## Cost Estimates

| Benchmark | Items | Approx. Cost | Time (single) |
|-----------|-------|--------------|---------------|
| GTEx | 191 | $7-10 | 2-3 hours |
| TCGA | 221 | $8-12 | 2-4 hours |
| PANDA | 197 | $7-10 | 2-3 hours |
| Expert VQA | 128 | $5-8 | 1-2 hours |
| SlideBench | 197 | $7-10 | 2-3 hours |

## Troubleshooting

### "WSI file not found"

```bash
# Check your WSI directory structure
giant check-data gtex -v
```

See [Data Acquisition](../data-acquisition.md) for download instructions.

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
