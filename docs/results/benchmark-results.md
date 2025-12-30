# Benchmark Results

This document tracks our MultiPathQA benchmark results and compares them to the published GIANT paper.

## GTEx Organ Classification (20-way)

**Date**: 2025-12-27
**Run ID**: `gtex_giant_openai_gpt-5.2`

### Our Results vs Paper

| Metric | Our Result | Paper (GPT-5 GIANT) | Paper (GPT-5 GIANT x5) |
|--------|------------|---------------------|------------------------|
| **Balanced Accuracy** | **67.6% ± 3.1%** | 53.7% | 60.7% |
| Bootstrap CI (95%) | 61.4% - 73.5% | - | - |
| Items Processed | 191/191 | 191 | 191 |
| Errors | 6 | - | - |
| Total Cost | $7.21 | - | - |

### Analysis

Our single-run result of **67.6%** exceeds the paper's single-run GIANT result (**53.7%**) and the paper's 5-run majority vote (**60.7%**). This is a strong validation that our implementation is working correctly.

**Possible reasons for improvement over paper:**
- We used `gpt-5.2` (latest) vs paper's `gpt-5` baseline
- Minor implementation differences in prompting or crop selection

### Comparison to Baselines (from paper)

| Method | GTEx Balanced Accuracy |
|--------|------------------------|
| **Our GIANT (gpt-5.2)** | **67.6%** |
| Paper: GIANT x5 (GPT-5) | 60.7% |
| Paper: GIANT x1 (GPT-5) | 53.7% |
| Paper: Thumbnail (GPT-5) | 36.5% |
| Paper: Patch (GPT-5) | 43.7% |
| Paper: TITAN | 96.3% |
| Paper: SlideChat | 5.0% |

Our implementation significantly outperforms the paper's thumbnail and patch baselines, but remains below specialized models like TITAN.

---

## Artifacts

### GTEx Result Files
- **Full Results JSON**: `results/gtex_giant_openai_gpt-5.2_results.json`
- **Checkpoint**: `results/checkpoints/gtex_giant_openai_gpt-5.2.checkpoint.json`
- **Log File**: `results/gtex-benchmark-20251227-010151.log`

### TCGA Result Files
- **Full Results JSON**: `results/tcga_giant_openai_gpt-5.2_results.json`
- **Checkpoint**: `results/checkpoints/tcga_giant_openai_gpt-5.2.checkpoint.json`

### PANDA Result Files
- **Full Results JSON**: `results/panda_giant_openai_gpt-5.2_results.json`
- **Checkpoint**: `results/checkpoints/panda_giant_openai_gpt-5.2.checkpoint.json`
- **Log File**: `results/panda_benchmark.log`

### Trajectory Files
Individual slide trajectories with full LLM reasoning are saved in:
```text
results/trajectories/GTEX-*_run0.json
```

Each trajectory contains:
- WSI path
- Question asked
- Turn-by-turn data:
  - Image shown to model (base64)
  - Model reasoning
  - Action taken (crop coordinates or answer)
- Final prediction
- Cost and token usage

---

## Summary Statistics

```json
{
  "metric_type": "balanced_accuracy",
  "point_estimate": 0.676,
  "bootstrap_mean": 0.676,
  "bootstrap_std": 0.031,
  "bootstrap_ci_lower": 0.614,
  "bootstrap_ci_upper": 0.735,
  "n_replicates": 1000,
  "n_total": 191,
  "n_errors": 6,
  "n_extraction_failures": 0
}
```

---

## TCGA Cancer Diagnosis (30-way)

**Date**: 2025-12-27
**Run ID**: `tcga_giant_openai_gpt-5.2`

### Our Results vs Paper

| Metric | Our Result | Paper (GPT-5 GIANT) | Paper (GPT-5 GIANT x5) |
|--------|------------|---------------------|------------------------|
| **Balanced Accuracy** | **25.2% ± 3.2%** | 32.3% | 29.3% |
| Bootstrap CI (95%) | 18.7% - 31.2% | - | - |
| Items Processed | 221/221 | 221 | 221 |
| Errors | 6 | - | - |
| Total Cost | $15.14 | - | - |

### Analysis

Our single-run result of **25.2%** is below the paper's single-run GIANT result (**32.3%**). This 30-way cancer classification task is significantly harder than GTEx's 20-way organ classification.

**Possible reasons for underperformance:**

1. **Task Difficulty**: Cancer diagnosis requires fine-grained cellular features that may need more navigation steps or specialized prompts
2. **Class Imbalance**: TCGA has 30 cancer types with uneven distribution
3. **Single-run variance**: In the paper, x5 majority voting (29.3%) did not improve over x1 (32.3%) for this task.

### Comparison to Baselines (from paper)

| Method | TCGA Balanced Accuracy |
|--------|------------------------|
| Paper: GIANT x5 (GPT-5) | 29.3% |
| Paper: GIANT x1 (GPT-5) | 32.3% |
| **Our GIANT (gpt-5.2)** | **25.2%** |
| Paper: Thumbnail (GPT-5) | 9.2% |
| Paper: Patch (GPT-5) | 12.8% |
| Paper: TITAN | 88.8% |
| Paper: SlideChat | 3.3% |

Our implementation outperforms the paper's thumbnail and patch baselines (9.2% and 12.8%), indicating the agent navigation is providing value, but there's room for improvement.

### Cost Efficiency

- **Cost per item**: $15.14 / 221 = ~$0.068/item
- **Average tokens per item**: 4,315,199 / 221 = ~19,525 tokens
- Approximately 1.8x more expensive per item than GTEx (likely due to more navigation steps)

---

## Summary Statistics (TCGA)

```json
{
  "metric_type": "balanced_accuracy",
  "point_estimate": 0.260,
  "bootstrap_mean": 0.252,
  "bootstrap_std": 0.032,
  "bootstrap_ci_lower": 0.187,
  "bootstrap_ci_upper": 0.312,
  "n_replicates": 1000,
  "n_total": 221,
  "n_errors": 6,
  "n_extraction_failures": 0
}
```

---

## PANDA Prostate Grading (6-way)

**Date**: 2025-12-29
**Run ID**: `panda_giant_openai_gpt-5.2`

### Our Results vs Paper

| Metric | Our Result | Paper (GPT-5 GIANT) | Paper (GPT-5 GIANT x5) |
|--------|------------|---------------------|------------------------|
| **Balanced Accuracy** | **19.7% ± 1.9%** (rescored; see below) | 23.2% | 25.4% |
| Bootstrap CI (95%) | 16.3% - 23.8% | - | - |
| Items Processed | 197/197 | 197 | 197 |
| Errors | 6 | - | - |
| Extraction Failures | 0 (rescored; 47 in pre-fix artifact) | - | - |
| Total Cost | $73.38 | - | - |

### Analysis

The original 2025-12-29 PANDA artifact scored **9.4% ± 2.2%** largely due to BUG-038-B1 (PANDA `"isup_grade": null` not mapping to benign label 0), which created 47 extraction failures and many mis-parsed labels via integer fallback.

Rescoring the saved PANDA predictions with the current fixed extractor (no new LLM calls) yields **19.7% ± 1.9%** balanced accuracy, while still including the 6 hard failures caused by BUG-038-B2 in the saved artifact.

Remaining gap vs paper (23.2%) is now much smaller; likely contributors include the 6 hard failures plus model/prompt differences.

### Comparison to Baselines (from paper)

| Method | PANDA Balanced Accuracy |
|--------|-------------------------|
| Paper: GIANT x5 (GPT-5) | 25.4% |
| Paper: GIANT x1 (GPT-5) | 23.2% |
| **Our GIANT (gpt-5.2)** | **19.7%** (rescored) |
| Paper: Thumbnail (GPT-5) | 17.9% |
| Paper: Patch (GPT-5) | 12.6% |
| Paper: TITAN | 59.9% |
| Paper: SlideChat | 16.7% |

### Recommended Next Step

Re-run PANDA with the BUG-038 fixes applied to eliminate the 6 B2 hard failures and to get accurate cost accounting (the saved artifact costs are a lower bound when parsing fails before usage is recorded).

---

## Summary Statistics (PANDA)

```json
{
  "metric_type": "balanced_accuracy",
  "point_estimate": 0.198,
  "bootstrap_mean": 0.197,
  "bootstrap_std": 0.019,
  "bootstrap_ci_lower": 0.163,
  "bootstrap_ci_upper": 0.238,
  "n_replicates": 1000,
  "n_total": 197,
  "n_errors": 6,
  "n_extraction_failures": 0
}
```

---

## Benchmark Summary

| Benchmark | Status | Our Result | Paper (x1) | Paper (x5) | Cost |
|-----------|--------|------------|------------|------------|------|
| GTEx (Organ, 20-way) | **COMPLETE** ✓ | **67.6%** | 53.7% | 60.7% | $7.21 |
| TCGA (Cancer Dx, 30-way) | **COMPLETE** ✓ | **25.2%** | 32.3% | 29.3% | $15.14 |
| PANDA (Grading, 6-way) | **COMPLETE** ✓ | **19.7%** (rescored) | 23.2% | 25.4% | $73.38 |
| ExpertVQA | Pending | - | 57.0% | 62.5% | - |
| SlideBenchVQA | Pending | - | 58.9% | 61.3% | - |

**Total E2E Validation Cost**: $95.73 (609 WSIs processed)

---

## Reproducibility

To reproduce these results:

```bash
# Ensure GTEx WSIs are in data/wsi/gtex/
uv run giant check-data gtex

# Run benchmark
source .env  # Load API keys
uv run giant benchmark gtex --provider openai --model gpt-5.2 -v
```

---

## Notes

1. **Cost Tracking**: Reported costs in the saved artifacts are lower bounds; parse-failed calls raised before usage/cost was accumulated (BUG-038-B2, now fixed for future runs).
2. **Error Rate**: The saved artifacts include 6 hard failures per benchmark due to BUG-038-B2 (now fixed in code); re-running will be needed to update GTEx/TCGA error-free scores.
3. **WSI Format**: Used DICOM format from IDC (OpenSlide 4.0.0+ compatible)
