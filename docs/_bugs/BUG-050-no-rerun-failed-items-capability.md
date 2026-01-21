# BUG-050: No "Rerun Failed Items Only" Capability

**Date**: 2026-01-21
**Severity**: P3 (Low) — quality-of-life improvement for evaluation workflow
**Status**: OPEN
**Discovered by**: Audit of GTEx 6 parse failures

## Summary

There is no built-in way to re-run ONLY the failed items from a benchmark run.
When items fail (due to parse errors, API errors, or other issues), users must
either:

1. Re-run the ENTIRE benchmark (expensive, time-consuming)
2. Manually construct a filtered item list and hack the runner (error-prone)

This is especially painful when:
- Failures are due to now-fixed bugs (like BUG-038-B2)
- API costs are significant ($7+ per GTEx run)
- Most items succeeded and don't need re-running

## Current Behavior

```bash
# To re-evaluate GTEx after fixing BUG-038-B2, you must:
giant benchmark gtex --provider openai --model gpt-5.2

# This re-runs ALL 191 items, even though only 6 failed
# Cost: ~$7.21 for 185 redundant items
```

## Proposed Behavior

```bash
# Option A: CLI flag
giant benchmark gtex --provider openai --model gpt-5.2 --recover-failures

# Option B: Explicit recover command
giant recover results/gtex_giant_openai_gpt-5.2_results.json

# Either would:
# 1. Load existing results
# 2. Identify items where error != null OR predicted_label == null
# 3. Re-run ONLY those items
# 4. Merge results back (replacing failed entries)
# 5. Recompute metrics
```

## Impact

### Current GTEx Situation

| Scenario | Items Run | Estimated Cost |
|----------|-----------|----------------|
| Full re-run (current) | 191 | ~$7.21 |
| Failed-only re-run (proposed) | 6 | ~$0.23 |
| **Savings** | 185 items | **~$6.98 (97%)** |

### Broader Impact

Across all benchmarks with ~3% failure rate (BUG-038-B2):
- TCGA: 6/221 failures
- GTEx: 6/191 failures
- PANDA: 6/197 failures

Total wasted cost for full re-runs: **~$20+** just to fix 18 items.

## Design Sketch

### Option A: `--recover-failures` flag

```python
# In src/giant/cli/commands/benchmark.py

@benchmark_cmd.command()
def run(
    dataset: str,
    recover_failures: bool = False,  # NEW
    ...
):
    if recover_failures:
        # Load existing results
        results_path = f"results/{dataset}_giant_{provider}_{model}_results.json"
        existing = load_results(results_path)

        # Filter to failed items
        failed_ids = {r.item_id for r in existing if r.error or r.predicted_label is None}

        # Run only failed items
        items = [i for i in all_items if i.item_id in failed_ids]

        # Merge back
        new_results = run_benchmark(items, ...)
        merged = merge_results(existing, new_results)
        save_results(merged, results_path)
```

### Option B: Standalone `recover` command

```python
# giant recover <results_file>

@cli.command()
def recover(results_file: Path):
    """Re-run failed items from a previous benchmark run."""
    existing = load_results(results_file)

    # Extract benchmark config from results
    config = existing.config

    # Identify failures
    failed = [r for r in existing.results if r.error or r.predicted_label is None]

    if not failed:
        print("No failures to recover!")
        return

    print(f"Found {len(failed)} failed items. Re-running...")

    # Re-run and merge
    ...
```

## Implementation Notes

1. **Checkpoints already exist**: The checkpoint system (`checkpoints/*.json`)
   already tracks which items have been processed. The recovery logic could
   leverage this.

2. **Idempotency**: Re-running should be safe. If an item now succeeds, it
   replaces the failed entry. If it fails again, it stays failed.

3. **Metrics recomputation**: After merging, metrics should be recomputed on
   the full (merged) result set.

4. **Cost tracking**: The new cost should be added to the existing total (not
   replaced).

## Acceptance Criteria

- [ ] A CLI option exists to re-run only failed items
- [ ] The option loads existing results and identifies failures
- [ ] Only failed items are sent to the LLM (not all items)
- [ ] Results are merged back correctly (replacing failed entries)
- [ ] Metrics are recomputed on the merged result set
- [ ] Cost is accumulated (existing + new)
- [ ] Documentation updated with recovery workflow

## Related

- **BUG-049**: Parse failures not recoverable (raw responses not persisted)
- **BUG-038-B2**: The JSON "Extra data" bug that caused the 6 failures (FIXED)

## Workaround (Current)

Until this is implemented, users can:

1. **Re-run full benchmark** (expensive but reliable)
2. **Manually filter**: Edit the benchmark CSV to include only failed items,
   run, then manually merge results (error-prone)
3. **Accept the failures**: Count them as incorrect for paper-faithful metrics
   (acceptable if failure rate is low)
