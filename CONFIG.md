# CONFIG.md — GIANT Configuration Registry

> **Single source of truth** for configurable CLI flags and environment variables.
> Updated: 2026-01-01

---

## Quick Reference: Paper Parity Commands

**These are the commands to run for paper-comparable benchmarks:**

```bash
# Paper-fidelity GIANT (T=20, fixed iterations)
uv run giant benchmark tcga --mode giant -T 20 --enforce-fixed-iterations

# Paper-fidelity patch baseline (30 calls + majority vote)
uv run giant benchmark tcga --mode patch_vote

# Thumbnail baseline (unchanged)
uv run giant benchmark tcga --mode thumbnail
```

---

## 1. CLI Flags

All CLI options are defined in `src/giant/cli/main.py`.

### 1.1 `giant benchmark`

| Argument / Flag | Default | Paper Parity | Description |
|-----------------|---------|--------------|-------------|
| `DATASET` | (required) | (required) | Dataset name (`tcga`, `panda`, `gtex`, `tcga_expert_vqa`, `tcga_slidebench`) |
| `--csv-path` | `data/multipathqa/MultiPathQA.csv` | any | Path to `MultiPathQA.csv` |
| `--wsi-root` | `data/wsi` | any | Root directory containing WSIs |
| `--output-dir, -o` | `results` | any | Output directory for results |
| `--mode, -m` | `giant` | `giant` or `patch_vote` | Evaluation mode. See [Modes](#modes) |
| `--provider, -p` | `openai` | any | LLM provider (`openai`, `anthropic`) |
| `--model` | `gpt-5.2` | varies | Model ID (see [Model Registry](#3-model-registry)). Note: if `--provider anthropic`, you must also set `--model` to an Anthropic-approved model. |
| `--max-steps, -T` | `20` | `20` | Max navigation steps (T parameter) |
| `--strict-font-check/--no-strict-font-check` | `False` | `False` | Fail if TrueType fonts are unavailable for axis labels |
| `--enforce-fixed-iterations/--no-enforce-fixed-iterations` | `False` | **`True`** | Reject early answers before the final step (paper-fidelity fixed-iteration mode) |
| `--runs, -r` | `1` | `1` | Runs per item for majority voting |
| `--concurrency, -c` | `4` | any | Max concurrent API calls |
| `--budget-usd` | `0.0` (disabled) | `0.0` | Stop early if total cost exceeds this USD budget (requires `--concurrency 1`) |
| `--max-items` | `0` (all) | `0` | Max items to evaluate (0 = all) |
| `--skip-missing/--no-skip-missing` | `True` | `True` | Skip missing WSI files |
| `--resume/--no-resume` | `True` | `True` | Resume from checkpoint |
| `--verbose, -v` | `0` | any | Increase verbosity (`-v`, `-vv`, `-vvv`). 0=WARNING, 1=INFO, 2+=DEBUG |
| `--json` | `False` | any | Output as JSON |

### Modes

| Mode | Description | Paper Section |
|------|-------------|---------------|
| `giant` | Full agentic navigation | Algorithm 1 |
| `thumbnail` | Single thumbnail, no navigation | Baseline |
| `patch` | 30-patch collage, single call | Our variant (fast) |
| `patch_vote` | 30 patches, 30 calls, majority vote | Paper baseline (Sec 4.2) |

---

### 1.2 `giant run`

Single-slide inference shares most flags with `benchmark`:

| Argument / Flag | Default | Description |
|-----------------|---------|-------------|
| `WSI_PATH` | (required) | Path to WSI file (`.svs`, `.ndpi`, `.tiff`) |
| `--question, -q` | (required) | Question to answer about the slide |
| `--mode, -m` | `giant` | Same modes as benchmark |
| `--provider, -p` | `openai` | LLM provider (`openai`, `anthropic`) |
| `--model` | `gpt-5.2` | Model ID (see [Model Registry](#3-model-registry)). Note: if `--provider anthropic`, you must also set `--model` to an Anthropic-approved model. |
| `--max-steps, -T` | `20` | Max navigation steps |
| `--strict-font-check/--no-strict-font-check` | `False` | Fail if TrueType fonts are unavailable for axis labels |
| `--enforce-fixed-iterations/--no-enforce-fixed-iterations` | `False` | Reject early answers (paper-fidelity fixed-iteration mode) |
| `--runs, -r` | `1` | Number of runs for majority voting |
| `--budget-usd` | `0.0` (disabled) | Stop early if total cost exceeds this USD budget (0 disables) |
| `--output, -o` | (none) | Save run artifact (trajectory + metadata) to JSON |
| `--verbose, -v` | `0` | Increase verbosity (`-v`, `-vv`, `-vvv`). 0=WARNING, 1=INFO, 2+=DEBUG |
| `--json` | `False` | Output as JSON |

---

### 1.3 `giant download`

| Argument / Flag | Default | Description |
|-----------------|---------|-------------|
| `DATASET` | `multipathqa` | Dataset to download (only `multipathqa` is supported) |
| `--output-dir, -o` | `data` | Output directory |
| `--force` | `False` | Re-download even if file exists |
| `--verbose, -v` | `0` | Increase verbosity (`-v`, `-vv`, `-vvv`). 0=WARNING, 1=INFO, 2+=DEBUG |
| `--json` | `False` | Output as JSON |

---

### 1.4 `giant check-data`

| Argument / Flag | Default | Description |
|-----------------|---------|-------------|
| `DATASET` | (required) | Dataset name (`tcga`, `panda`, `gtex`, `tcga_expert_vqa`, `tcga_slidebench`) |
| `--csv-path` | `data/multipathqa/MultiPathQA.csv` | Path to `MultiPathQA.csv` |
| `--wsi-root` | `data/wsi` | Root directory containing WSIs |
| `--verbose, -v` | `0` | Increase verbosity (`-v`, `-vv`, `-vvv`). 0=WARNING, 1=INFO, 2+=DEBUG |
| `--json` | `False` | Output as JSON |

---

### 1.5 `giant visualize`

| Argument / Flag | Default | Description |
|-----------------|---------|-------------|
| `TRAJECTORY_PATH` | (required) | Path to trajectory JSON file |
| `--output, -o` | (none) | Output HTML file path |
| `--open/--no-open` | `True` | Open visualization in browser |
| `--verbose, -v` | `0` | Increase verbosity (`-v`, `-vv`, `-vvv`). 0=WARNING, 1=INFO, 2+=DEBUG |
| `--json` | `False` | Output as JSON |

---

### 1.6 `giant version`

| Flag | Default | Description |
|------|---------|-------------|
| `--json` | `False` | Output as JSON |

---

## 2. Environment Variables (.env)

Copy `.env.example` to `.env` and configure:

All environment variables are declared in `src/giant/config.py` (`Settings`) and are
case-sensitive.

| Variable | Default | Used By | Description |
|----------|---------|---------|-------------|
| `OPENAI_API_KEY` | (unset) | `src/giant/llm/openai_client.py` | OpenAI API key |
| `ANTHROPIC_API_KEY` | (unset) | `src/giant/llm/anthropic_client.py` | Anthropic API key |
| `GOOGLE_API_KEY` | (unset) | (unused) | Google/Gemini API key (provider not implemented) |
| `HUGGINGFACE_TOKEN` | (unset) | `src/giant/data/download.py` | Token for gated HuggingFace datasets |
| `LOG_LEVEL` | `INFO` | `src/giant/utils/logging.py` | Default log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `LOG_FORMAT` | `console` | `src/giant/utils/logging.py` | Log format (`console`, `json`) |
| `WSI_LONG_SIDE_TARGET` | `1000` | `src/giant/config.py` | Paper S parameter (crop target size). If set, overrides default `IMAGE_SIZE_OPENAI`/`IMAGE_SIZE_ANTHROPIC` unless provider-specific values are set. |
| `MAX_ITERATIONS` | `20` | `src/giant/cli/main.py`, `src/giant/agent/runner.py`, `src/giant/eval/runner.py` | Paper T parameter (default max steps). Used when CLI/config does not specify `max_steps`. |
| `OVERSAMPLING_BIAS` | `0.85` | `src/giant/agent/runner.py` | Crop oversampling bias passed into `CropEngine.crop(..., bias=...)`. |
| `THUMBNAIL_SIZE` | `1024` | `src/giant/agent/runner.py` | Default thumbnail long side (`AgentConfig.thumbnail_size`). |
| `PATCH_SIZE` | `224` | `src/giant/cli/runners.py`, `src/giant/eval/executor.py` | Patch size for baselines. |
| `PATCH_COUNT` | `30` | `src/giant/cli/runners.py`, `src/giant/eval/executor.py` | Patch count for baselines. |
| `BOOTSTRAP_REPLICATES` | `1000` | `src/giant/eval/runner.py` | Bootstrap samples for uncertainty reporting. |
| `JPEG_QUALITY` | `85` | `src/giant/core/crop_engine.py` | JPEG quality (1–100) for encoded images |
| `IMAGE_SIZE_OPENAI` | `1000` | `src/giant/llm/openai_client.py` | Target long-side for OpenAI images |
| `IMAGE_SIZE_ANTHROPIC` | `500` | `src/giant/llm/anthropic_client.py` | Target long-side for Anthropic images (pricing) |
| `OPENAI_RPM` | `60` | `src/giant/llm/openai_client.py` | Rate limit (requests/min) |
| `ANTHROPIC_RPM` | `60` | `src/giant/llm/anthropic_client.py` | Rate limit (requests/min) |
| `DEFAULT_BUDGET_USD` | `0.0` | (unused) | Default budget guardrail (0 = disabled). CLI defaults come from `src/giant/cli/main.py`. |
| `GIANT_SYSTEM_PROMPT` | (unset) | `src/giant/config.py` | Global system prompt override (inline) |
| `GIANT_SYSTEM_PROMPT_PATH` | (unset) | `src/giant/config.py` | Global system prompt override (file path) |
| `GIANT_SYSTEM_PROMPT_OPENAI` | (unset) | `src/giant/config.py` | OpenAI-specific system prompt override |
| `GIANT_SYSTEM_PROMPT_OPENAI_PATH` | (unset) | `src/giant/config.py` | OpenAI-specific system prompt override (file path) |
| `GIANT_SYSTEM_PROMPT_ANTHROPIC` | (unset) | `src/giant/config.py` | Anthropic-specific system prompt override |
| `GIANT_SYSTEM_PROMPT_ANTHROPIC_PATH` | (unset) | `src/giant/config.py` | Anthropic-specific system prompt override (file path) |

Precedence: Provider-specific PATH > Provider-specific value > Global PATH > Global value

---

## 3. Model Registry

Approved models are enforced at runtime. See `docs/models/model-registry.md`.

| Provider | Default Model | Notes |
|----------|---------------|-------|
| OpenAI | `gpt-5.2` | 2025 frontier |
| Anthropic | `claude-sonnet-4-5-20250929` | 2025 frontier |
| Google | `gemini-3-pro-preview` | Provider not yet implemented |

---

## 4. AgentConfig (Programmatic)

When using GIANT as a library:

| Field | Type | Default | CLI Flag | Description |
|-------|------|---------|----------|-------------|
| `max_steps` | `int` | `20` | `--max-steps, -T` | Maximum navigation steps (T in Algorithm 1) |
| `max_retries` | `int` | `3` | (none) | Max consecutive errors before termination |
| `budget_usd` | `Optional[float]` | `None` | `--budget-usd` (run only) | Optional cost limit (force answer if exceeded) |
| `thumbnail_size` | `int` | `1024` | (none) | Thumbnail max size for axis-guide image |
| `force_answer_retries` | `int` | `3` | (none) | Retries when forcing answer at max steps |
| `strict_font_check` | `bool` | `False` | `--strict-font-check/--no-strict-font-check` | Fail if axis label fonts are unavailable |
| `enable_conch` | `bool` | `False` | (none) | Enable CONCH tool usage |
| `conch_scorer` | `Optional[ConchScorer]` | `None` | (none) | Optional CONCH scorer implementation |
| `system_prompt` | `Optional[str]` | `None` | (none) | Optional system prompt override |
| `enforce_fixed_iterations` | `bool` | `False` | `--enforce-fixed-iterations/--no-enforce-fixed-iterations` | Reject early answers before the final step |

```python
from giant.agent.runner import AgentConfig, GIANTAgent

config = AgentConfig(
    max_steps=20,                    # T parameter (default: 20)
    max_retries=3,                   # Retries on errors (default: 3)
    budget_usd=None,                 # Cost limit (default: None)
    thumbnail_size=1024,             # Thumbnail size (default: 1024)
    force_answer_retries=3,          # Retries when forcing answer (default: 3)
    strict_font_check=False,         # Font validation (default: False)
    enable_conch=False,              # CONCH tool (default: False)
    conch_scorer=None,               # Custom CONCH scorer
    system_prompt=None,              # Prompt override
    enforce_fixed_iterations=False,  # Paper fidelity mode (default: False)
)
```

---

## 5. EvaluationConfig (Programmatic)

For batch evaluation:

| Field | Type | Default | CLI Flag | Description |
|-------|------|---------|----------|-------------|
| `mode` | `Literal[...]` | `"giant"` | `--mode, -m` | Evaluation mode (`giant`, `thumbnail`, `patch`, `patch_vote`) |
| `max_steps` | `int` | `20` | `--max-steps, -T` | Max navigation steps per item |
| `runs_per_item` | `int` | `1` | `--runs, -r` | Runs per item for majority voting |
| `max_concurrent` | `int` | `4` | `--concurrency, -c` | Max concurrent item executions |
| `max_items` | `Optional[int]` | `None` | `--max-items` | Optional cap on number of items |
| `skip_missing_wsis` | `bool` | `False` | `--skip-missing/--no-skip-missing` | Skip items whose WSI is missing |
| `budget_usd` | `Optional[float]` | `None` | `--budget-usd` | Optional total budget across the run (requires `max_concurrent=1`) |
| `strict_font_check` | `bool` | `False` | `--strict-font-check/--no-strict-font-check` | Fail if axis label fonts are unavailable |
| `enforce_fixed_iterations` | `bool` | `False` | `--enforce-fixed-iterations/--no-enforce-fixed-iterations` | Reject early answers before the final step |
| `save_trajectories` | `bool` | `True` | (none) | Persist trajectories to `output_dir` |
| `checkpoint_interval` | `int` | `10` | (none) | Save checkpoint every N completed items |
| `bootstrap_replicates` | `int` | `1000` | (none) | Bootstrap replicates for uncertainty reporting |

```python
from giant.eval.runner import EvaluationConfig

config = EvaluationConfig(
    mode="giant",                    # "giant", "thumbnail", "patch", "patch_vote"
    max_steps=20,                    # T parameter
    runs_per_item=1,                 # Majority voting runs
    max_concurrent=4,                # Concurrency limit
    max_items=None,                  # Item limit (None = all)
    skip_missing_wsis=False,         # Skip missing WSIs
    budget_usd=None,                 # Total cost limit
    strict_font_check=False,         # Font validation
    enforce_fixed_iterations=False,  # Paper fidelity mode
    save_trajectories=True,          # Save trajectories
    checkpoint_interval=10,          # Checkpoint frequency
)
```

---

## 6. Paper Parity Checklist

Before running a paper-comparable benchmark:

- [ ] **Mode**: Use `--mode giant` or `--mode patch_vote` (not `patch`)
- [ ] **Steps**: Use `-T 20` (paper default)
- [ ] **Fixed iterations**: Use `--enforce-fixed-iterations` for GIANT mode
- [ ] **Model**: Use approved frontier model (`gpt-5.2`, `claude-sonnet-4-5-20250929`)
- [ ] **Full dataset**: Use `--max-items 0` (all items)
- [ ] **WSI data**: Ensure all WSIs are downloaded (run `giant check-data <dataset>`)

### Example: Full Paper Parity Run

```bash
# 1. Verify data
uv run giant check-data tcga
uv run giant check-data panda
uv run giant check-data gtex

# 2. Run GIANT with fixed iterations (paper-fidelity)
uv run giant benchmark tcga --mode giant -T 20 --enforce-fixed-iterations

# 3. Run paper-fidelity patch baseline
uv run giant benchmark tcga --mode patch_vote

# 4. Run thumbnail baseline
uv run giant benchmark tcga --mode thumbnail
```

---

## 7. Common Gotchas

### Early stopping without `--enforce-fixed-iterations`

Without this flag, the model can answer at any step. Our benchmarks show:
- TCGA: Mean 3.92 steps (configured for 20)
- PANDA: Mean 10.28 steps (configured for 20)

The paper shows accuracy improves up to T=20. Use `--enforce-fixed-iterations` for comparable results.

### `patch` vs `patch_vote`

| Mode | Calls | Paper-comparable |
|------|-------|------------------|
| `patch` | 1 (collage) | No |
| `patch_vote` | 30 (individual) | Yes |

### Budget with concurrency

For benchmarks, `--budget-usd` requires `--concurrency 1` (enforced by
`EvaluationConfig` validation). If you set `--budget-usd` with `--concurrency > 1`,
the run errors out.

---

## 8. Wiring Check (Paper Parity Flag)

Trace for `--enforce-fixed-iterations`:

CLI (`src/giant/cli/main.py`) → `run_benchmark(...)` (`src/giant/cli/runners.py`) →
`EvaluationConfig.enforce_fixed_iterations` (`src/giant/eval/runner.py`) →
`AgentConfig.enforce_fixed_iterations` (`src/giant/eval/executor.py` → `src/giant/agent/runner.py`) →
`ContextManager.enforce_fixed_iterations` (`src/giant/agent/context.py`) →
`PromptBuilder(enforce_fixed_iterations=...)` (`src/giant/prompts/builder.py` +
`src/giant/prompts/templates.py`).

---

## 9. File Locations

| File | Purpose |
|------|---------|
| `.env` | Environment variables (gitignored) |
| `.env.example` | Template for `.env` |
| `src/giant/config.py` | Settings class |
| `src/giant/cli/main.py` | CLI definitions |
| `src/giant/agent/runner.py` | AgentConfig |
| `src/giant/eval/runner.py` | EvaluationConfig |
| `docs/models/model-registry.md` | Approved models |

---

## Changelog

- **2026-01-01**: Added `--enforce-fixed-iterations` (BUG-041), `--mode patch_vote` (BUG-042)
- **2026-01-01**: Initial registry created
