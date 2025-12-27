# Spec-11.5: End-to-End Validation Checkpoint

## Overview

This is a **mandatory checkpoint** before proceeding to Spec-12 (CLI & API Surface). The purpose is to validate that the entire GIANT system works end-to-end with real WSI files from the MultiPathQA benchmark.

**Why This Matters:** We have built all the components (WSI reader, LLM providers, agent loop, evaluation framework, CLAM integration) but have only tested them in isolation with mocks and a single test WSI. This checkpoint ensures the system actually works on the benchmark data before we build the final CLI/API layer.

> **Critical Lesson:** This checkpoint should have been executed earlier, ideally after each major integration (Spec-05.5, Spec-08.5). We proceeded too far with unit tests and mocks without validating against real benchmark data.

## Dependencies

- [Spec-09: GIANT Agent Core Loop](./spec-09-giant-agent.md) - Agent must be functional
- [Spec-10: Evaluation & Benchmarking](./spec-10-evaluation.md) - Metrics and runner implemented
- [Spec-11: CLAM Integration](./spec-11-clam-integration.md) - Tissue segmentation for baseline
- [data-acquisition.md](../data-acquisition.md) - WSIs must be downloaded

## MultiPathQA Benchmark Summary

The benchmark contains **5 distinct tasks** spanning 3 data sources:

| Benchmark | Questions | Unique WSIs | Task | Source |
|-----------|-----------|-------------|------|--------|
| `tcga` | 221 | 221 | Cancer Diagnosis (30-way) | TCGA |
| `tcga_expert_vqa` | 128 | 76 | Pathologist-Authored VQA | TCGA |
| `tcga_slidebench` | 197 | 183 | SlideBench VQA | TCGA |
| `gtex` | 191 | 191 | Organ Classification (20-way) | GTEx |
| `panda` | 197 | 197 | Prostate Grading (6-way) | PANDA |
| **Total** | **934** | **862** | - | - |

**WSI Files Required:**
- TCGA: **474** `.svs` files (all 3 TCGA benchmarks combined)
- GTEx: **191** `.tiff` files
- PANDA: **197** `.tiff` files
- **Total: 862 unique WSI files (TCGA alone is ~472 GiB; total is many hundreds of GiB)**

File lists are provided in `data/wsi/{tcga,gtex,panda}_files.txt`.

## Pre-Requisites

Before running this checkpoint, you MUST have:

1. **Downloaded at least a subset of WSIs** from each benchmark:
   - [ ] At least 5 TCGA slides in `data/wsi/tcga/` (see `data/wsi/tcga_files.txt`)
   - [ ] At least 5 GTEx slides in `data/wsi/gtex/` (see `data/wsi/gtex_files.txt`)
   - [ ] At least 5 PANDA slides in `data/wsi/panda/` (see `data/wsi/panda_files.txt`)

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

  wsi_root = Path('data/wsi')
  for subdir in ['tcga', 'gtex', 'panda']:
      dir_path = wsi_root / subdir
      if not dir_path.exists():
          print(f'{subdir}: directory not found')
          continue

      wsi_files = list(dir_path.rglob('*.svs')) + list(dir_path.rglob('*.tiff'))
      print(f'{subdir}: {len(wsi_files)} files found')

      for wsi in wsi_files[:3]:  # Test first 3
          try:
              with WSIReader(wsi) as r:
                  meta = r.get_metadata()
                  print(f'  {wsi.name}: {meta.width}x{meta.height}, {meta.level_count} levels')
          except Exception as e:
              print(f'  {wsi.name}: ERROR - {e}')
  "
  ```

- [ ] **Cropping pipeline works at all levels:**
  ```bash
  python -c "
  from giant.core import CropEngine
  from giant.wsi import WSIReader
  from giant.geometry import Region
  from pathlib import Path

  # Find a TCGA slide
  tcga_dir = Path('data/wsi/tcga')
  wsi_file = next(tcga_dir.rglob('*.svs'), None)
  if not wsi_file:
      print('No TCGA slides found')
      exit(1)

  with WSIReader(wsi_file) as reader:
      meta = reader.get_metadata()
      # Crop from center
      region = Region(
          x=meta.width // 4,
          y=meta.height // 4,
          width=meta.width // 2,
          height=meta.height // 2
      )
      engine = CropEngine(reader)
      cropped = engine.crop(region, target_size=1000)
      print(f'Source: {wsi_file.name}')
      print(f'Region: {region}')
      print(f'Crop shape: {cropped.image.size}')
      cropped.image.save('/tmp/test_crop.png')
      print('Saved to /tmp/test_crop.png')
  "
  ```

### Phase 2: Tissue Segmentation Validation

- [ ] **CLAM parity segmentation works:**
  ```bash
  python -c "
  from giant.wsi import WSIReader
  from giant.vision import TissueSegmentor
  import numpy as np
  from pathlib import Path

  tcga_dir = Path('data/wsi/tcga')
  wsi_file = next(tcga_dir.rglob('*.svs'), None)
  if not wsi_file:
      print('No TCGA slides found')
      exit(1)

  with WSIReader(wsi_file) as reader:
      thumb = reader.get_thumbnail((2048, 2048))
      segmentor = TissueSegmentor()
      mask = segmentor.segment(thumb)
      tissue_pct = np.mean(mask) * 100
      print(f'Source: {wsi_file.name}')
      print(f'Thumbnail size: {thumb.size}')
      print(f'Tissue coverage: {tissue_pct:.1f}%')
  "
  ```

- [ ] **Random patch sampling works:**
  ```bash
  python -c "
  from giant.wsi import WSIReader
  from giant.vision import TissueSegmentor, sample_patches
  from pathlib import Path

  tcga_dir = Path('data/wsi/tcga')
  wsi_file = next(tcga_dir.rglob('*.svs'), None)
  if not wsi_file:
      print('No TCGA slides found')
      exit(1)

  with WSIReader(wsi_file) as reader:
      meta = reader.get_metadata()
      thumb = reader.get_thumbnail((2048, 2048))
      segmentor = TissueSegmentor()
      mask = segmentor.segment(thumb)
      patches = sample_patches(mask, meta, n_patches=10)
      print(f'Source: {wsi_file.name}')
      print(f'Sampled {len(patches)} patches')
      for p in patches[:3]:
          print(f'  Region: ({p.x}, {p.y}) - {p.width}x{p.height}')
  "
  ```

### Phase 3: Agent Loop Validation

- [ ] **Agent can navigate a real WSI:**
  ```bash
  # Run agent on a single slide (costs vary by model/steps)
  python -c "
  import asyncio
  from giant.llm import create_provider
  from giant.agent import AgentConfig, GIANTAgent
  from pathlib import Path

  provider = create_provider('anthropic')  # or 'openai'

  tcga_dir = Path('data/wsi/tcga')
  wsi_file = next(tcga_dir.rglob('*.svs'), None)
  if not wsi_file:
      print('No TCGA slides found')
      raise SystemExit(1)

  async def main() -> None:
      agent = GIANTAgent(
          wsi_path=wsi_file,
          question='What type of cancer is shown in this slide?',
          llm_provider=provider,
          config=AgentConfig(max_steps=5),
      )
      result = await agent.run()
      print(f'Source: {wsi_file.name}')
      print(f'Success: {result.success}')
      print(f'Answer: {result.answer}')
      print(f'Turns: {len(result.trajectory.turns)}')
      print(f'Cost: \${result.total_cost:.4f}')
      if result.error_message:
          print(f'Error: {result.error_message}')

  asyncio.run(main())
  "
  ```

### Phase 4: Evaluation Pipeline Validation

- [ ] **Benchmark runner can process items from all 5 benchmarks:**
  ```bash
  # Run on up to 2 items from each benchmark (costs vary).
  # If you only have a subset of WSIs locally, this will skip missing slides.
  python -c "
  import asyncio
  from pathlib import Path

  from giant.eval.runner import BenchmarkRunner, EvaluationConfig
  from giant.llm import create_provider

  async def main() -> None:
      provider = create_provider('anthropic')  # or 'openai'
      runner = BenchmarkRunner(
          llm_provider=provider,
          wsi_root=Path('data/wsi'),
          output_dir=Path('results/e2e_validation'),
          config=EvaluationConfig(
              max_steps=5,
              max_concurrent=1,
              max_items=2,
              skip_missing_wsis=True,
          ),
      )

      csv_path = Path('data/multipathqa/MultiPathQA.csv')
      benchmarks = ['tcga', 'tcga_expert_vqa', 'tcga_slidebench', 'gtex', 'panda']

      for bm in benchmarks:
          results = await runner.run_benchmark(
              benchmark_name=bm,
              csv_path=csv_path,
              run_id=f'e2e_{bm}',
          )
          print(f\"{bm}: {results.metrics}\")

  asyncio.run(main())
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
  # Full TCGA cancer diagnosis benchmark (~$50-100, ~2-4 hours)
  python -c "
  import asyncio
  from pathlib import Path

  from giant.eval.runner import BenchmarkRunner, EvaluationConfig
  from giant.llm import create_provider

  async def main() -> None:
      provider = create_provider('anthropic')  # or 'openai'
      runner = BenchmarkRunner(
          llm_provider=provider,
          wsi_root=Path('data/wsi'),
          output_dir=Path('results/tcga_full'),
          config=EvaluationConfig(max_steps=20),
      )
      await runner.run_benchmark(
          benchmark_name='tcga',
          csv_path=Path('data/multipathqa/MultiPathQA.csv'),
          run_id='tcga_full',
      )

  asyncio.run(main())
  "
  ```

- [ ] **Compare results to paper baseline:**

  Paper reports for GPT-5 + GIANT on main benchmarks:
  | Benchmark | Paper Result | Expected Range |
  |-----------|--------------|----------------|
  | TCGA (cancer diagnosis) | 32.3% | 25-40% |
  | GTEx (organ classification) | 60.7% | 50-70% |
  | PANDA (prostate grading) | 25.4% | 18-35% |
  | Expert VQA | 62.5% | 50-75% |
  | SlideBench VQA | 58.9% | 45-70% |

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
- TCGA slides: N / 474
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
- Results:
  - tcga: X%
  - tcga_expert_vqa: X%
  - tcga_slidebench: X%
  - gtex: X%
  - panda: X%
- Notes:

### Phase 5: Full Benchmark (if run)
- Benchmark: [name]
- Result: X% +/- Y%
- Paper baseline: Z% +/- W%
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
| Basic (Phase 1-4) | 5 per source | $2-5 | 30 min |
| Full (Phase 1-5) | All 862 | $50-150 | 4-8 hours |

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
