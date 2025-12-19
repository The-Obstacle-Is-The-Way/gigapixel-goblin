# Spec-11.5: End-to-End Validation Checkpoint

## Overview

This is a **mandatory checkpoint** before proceeding to Spec-12 (CLI & API Surface). The purpose is to validate that the entire GIANT system works end-to-end with real WSI files from the MultiPathQA benchmark.

**Why This Matters:** We have built all the components (WSI reader, LLM providers, agent loop, evaluation framework, CLAM integration) but have only tested them in isolation with mocks and a single test WSI. This checkpoint ensures the system actually works on the benchmark data before we build the final CLI/API layer.

> **Critical Lesson:** This checkpoint should have been executed earlier, ideally after each major integration (Spec-05.5, Spec-08.5). We proceeded too far with unit tests and mocks without validating against real benchmark data.

## Dependencies

- [Spec-09: GIANT Agent Core Loop](./spec-09-giant-agent.md) - Agent must be functional
- [Spec-10: Evaluation & Benchmarking](./spec-10-evaluation.md) - Metrics and runner implemented
- [Spec-11: CLAM Integration](./spec-11-clam-integration.md) - Tissue segmentation for baseline
- [DATA_ACQUISITION.md](../DATA_ACQUISITION.md) - WSIs must be downloaded

## Pre-Requisites

Before running this checkpoint, you MUST have:

1. **Downloaded at least a subset of WSIs** from each benchmark:
   - [ ] At least 5 TCGA slides in `data/wsi/tcga/`
   - [ ] At least 5 GTEx slides in `data/wsi/gtex/`
   - [ ] At least 5 PANDA slides in `data/wsi/panda/`

2. **Configured API keys** for at least one LLM provider:
   - [ ] `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` in `.env`

3. **Verified OpenSlide installation:**
   ```bash
   python -c "import openslide; print(openslide.__version__)"
   ```

## Acceptance Criteria

### Phase 1: WSI Pipeline Validation

- [ ] **WSI Reader works on real files:**
  ```bash
  # For each downloaded WSI, verify it can be opened and read
  python -c "
  from giant.wsi import WSIReader
  from pathlib import Path

  for wsi in Path('data/wsi').rglob('*.svs'):
      with WSIReader(wsi) as r:
          meta = r.get_metadata()
          print(f'{wsi.name}: {meta.width}x{meta.height}, {meta.level_count} levels')
          thumb = r.get_thumbnail((512, 512))
          print(f'  Thumbnail: {thumb.size}')
  "
  ```

- [ ] **Cropping pipeline works at all levels:**
  ```bash
  python -c "
  from giant.wsi import WSIReader
  from giant.crop import crop_region
  from giant.geometry import Region

  with WSIReader('data/wsi/tcga/some_slide.svs') as reader:
      region = Region(x=1000, y=1000, width=2000, height=2000)
      crop = crop_region(reader, region, target_size=1000)
      print(f'Crop shape: {crop.size}')
      crop.save('/tmp/test_crop.png')
  "
  ```

### Phase 2: Tissue Segmentation Validation

- [ ] **CLAM parity segmentation works:**
  ```bash
  python -c "
  from giant.wsi import WSIReader
  from giant.vision import TissueSegmentor
  import numpy as np

  with WSIReader('data/wsi/tcga/some_slide.svs') as reader:
      thumb = reader.get_thumbnail((2048, 2048))
      segmentor = TissueSegmentor(backend='parity')
      mask = segmentor.segment(thumb)
      tissue_pct = np.mean(mask > 0) * 100
      print(f'Tissue coverage: {tissue_pct:.1f}%')
  "
  ```

- [ ] **Random patch sampling works:**
  ```bash
  python -c "
  from giant.wsi import WSIReader
  from giant.vision import TissueSegmentor, sample_patches

  with WSIReader('data/wsi/tcga/some_slide.svs') as reader:
      meta = reader.get_metadata()
      thumb = reader.get_thumbnail((2048, 2048))
      mask = TissueSegmentor().segment(thumb)
      patches = sample_patches(mask, meta, n_patches=10)
      print(f'Sampled {len(patches)} patches')
      for p in patches[:3]:
          print(f'  Region: ({p.x}, {p.y}) - {p.width}x{p.height}')
  "
  ```

### Phase 3: Agent Loop Validation

- [ ] **Agent can navigate a real WSI:**
  ```bash
  # Run agent on a single slide (costs ~$0.10-0.50 depending on iterations)
  python -c "
  from giant.agent import GIANTAgent
  from giant.wsi import WSIReader
  from giant.llm import create_provider

  provider = create_provider('anthropic')  # or 'openai'

  with WSIReader('data/wsi/tcga/some_slide.svs') as reader:
      agent = GIANTAgent(reader, provider)
      result = agent.run(
          question='What type of cancer is shown in this slide?',
          max_iterations=5,
      )
      print(f'Answer: {result.answer}')
      print(f'Iterations: {len(result.trajectory)}')
      print(f'Cost: \${result.cost_usd:.4f}')
  "
  ```

### Phase 4: Evaluation Pipeline Validation

- [ ] **Benchmark runner can process items:**
  ```bash
  # Run on 3 items from each benchmark (costs ~$1-5)
  python -c "
  from giant.eval import BenchmarkRunner, EvaluationConfig

  config = EvaluationConfig(
      wsi_root='data/wsi',
      provider='anthropic',
      max_iterations=5,
      sample_size=3,  # Only 3 items per benchmark for validation
  )

  runner = BenchmarkRunner(config)
  results = runner.run(benchmarks=['tcga', 'gtex', 'panda'])

  for r in results:
      print(f'{r.benchmark}: {r.accuracy:.1%} ({r.correct}/{r.total})')
  "
  ```

- [ ] **Metrics calculation is correct:**
  ```bash
  # Verify accuracy and balanced accuracy compute correctly
  python -c "
  from giant.eval.metrics import accuracy, balanced_accuracy

  # Perfect case
  preds = [1, 2, 3, 4, 5]
  truth = [1, 2, 3, 4, 5]
  assert accuracy(preds, truth) == 1.0

  # Imbalanced case (should penalize biased classifier)
  preds = [1, 1, 1, 1, 1]  # Always predicts 1
  truth = [1, 1, 1, 1, 2]  # But class 2 exists
  assert accuracy(preds, truth) == 0.8
  assert balanced_accuracy(preds, truth) == 0.5
  print('Metrics validation passed')
  "
  ```

### Phase 5: Full Benchmark Run (Optional but Recommended)

- [ ] **Run full benchmark on one task:**
  ```bash
  # Full TCGA benchmark run (~$50-100, ~2-4 hours)
  giant eval --benchmark tcga --wsi-root data/wsi --output results/tcga_full.json
  ```

- [ ] **Compare results to paper baseline:**
  Paper reports for GPT-5 + GIANT on TCGA: 32.3% ± 3.5%
  Your result should be within reasonable range (25-40%).

## Validation Report Template

After completing the checkpoint, create a validation report:

```markdown
# E2E Validation Report

**Date:** YYYY-MM-DD
**Tester:** [Name]

## Environment
- Python: X.Y.Z
- OpenSlide: X.Y.Z
- LLM Provider: [anthropic/openai]
- Model: [claude-sonnet-4-20250514/gpt-5]

## WSI Data
- TCGA slides: N / 221
- GTEx slides: N / 191
- PANDA slides: N / 197

## Results

### Phase 1: WSI Pipeline
- [ ] Pass / [ ] Fail
- Notes:

### Phase 2: Segmentation
- [ ] Pass / [ ] Fail
- Notes:

### Phase 3: Agent Loop
- [ ] Pass / [ ] Fail
- Cost: $X.XX
- Notes:

### Phase 4: Evaluation
- [ ] Pass / [ ] Fail
- Results: TCGA X%, GTEx Y%, PANDA Z%
- Notes:

### Phase 5: Full Benchmark (if run)
- Benchmark: [name]
- Result: X% ± Y%
- Paper baseline: Z% ± W%
- Within expected range: [Yes/No]

## Issues Found
1. [Issue description]
2. [Issue description]

## Sign-off
- [ ] All critical phases passed
- [ ] Ready to proceed to Spec-12
```

## Estimated Costs

| Validation Level | WSIs Needed | API Cost | Time |
|------------------|-------------|----------|------|
| Minimal (Phase 1-2) | 5 per source | $0 | 10 min |
| Basic (Phase 1-4) | 5 per source | $1-5 | 30 min |
| Full (Phase 1-5) | All 609 | $50-150 | 4-8 hours |

## What to Do If Validation Fails

1. **WSI read errors:** Check OpenSlide installation, file permissions, file corruption
2. **Segmentation errors:** Check image mode (must be RGB), check mask dimensions
3. **Agent errors:** Check API keys, rate limits, prompt formatting
4. **Metric mismatches:** Check answer extraction logic, verify truth labels from CSV

## Post-Checkpoint Actions

Once all phases pass:

1. [ ] Create validation report and save to `docs/validation/`
2. [ ] Commit report to repository
3. [ ] Proceed to Spec-12: CLI & API Surface

If phases fail:

1. [ ] Document the failure mode
2. [ ] Create a bug report in `docs/bugs/`
3. [ ] Fix the issue before proceeding
4. [ ] Re-run validation
