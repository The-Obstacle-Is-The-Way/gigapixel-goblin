# CONFIG.md — GIANT Configuration Registry

> **Single source of truth** for all configurable flags, environment variables, and CLI options.
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

## 1. CLI Flags (giant benchmark)

| Flag | Default | Paper Parity | Description |
|------|---------|--------------|-------------|
| `--mode` | `giant` | `giant` or `patch_vote` | Evaluation mode. See [Modes](#modes) |
| `-T, --max-steps` | `20` | `20` | Navigation budget (T parameter) |
| `--enforce-fixed-iterations` | `False` | **`True`** | Reject early answers before final step |
| `-p, --provider` | `openai` | `openai` | LLM provider (`openai`, `anthropic`) |
| `--model` | `gpt-5.2` | varies | Model ID (see [Model Registry](#model-registry)) |
| `-r, --runs` | `1` | `1` | Runs per item for majority voting |
| `-c, --concurrency` | `4` | any | Max concurrent API calls |
| `--budget-usd` | `0` (none) | `0` | Stop early if cost exceeds budget |
| `--max-items` | `0` (all) | `0` | Limit items (for smoke tests) |
| `--skip-missing` | `True` | `True` | Skip missing WSI files |
| `--resume` | `True` | `True` | Resume from checkpoint |
| `--strict-font-check` | `False` | `False` | Fail if TrueType fonts unavailable |
| `-v, --verbose` | `0` | any | Verbosity (0=WARN, 1=INFO, 2+=DEBUG) |
| `--json` | `False` | any | Output as JSON |

### Modes

| Mode | Description | Paper Section |
|------|-------------|---------------|
| `giant` | Full agentic navigation | Algorithm 1 |
| `thumbnail` | Single thumbnail, no navigation | Baseline |
| `patch` | 30-patch collage, single call | Our variant (fast) |
| `patch_vote` | 30 patches, 30 calls, majority vote | Paper baseline (Sec 4.2) |

---

## 2. CLI Flags (giant run)

Single-slide inference shares most flags with `benchmark`:

| Flag | Default | Description |
|------|---------|-------------|
| `-q, --question` | (required) | Question about the slide |
| `--mode` | `giant` | Same modes as benchmark |
| `-T, --max-steps` | `20` | Navigation budget |
| `--enforce-fixed-iterations` | `False` | Fixed iteration mode |
| `-p, --provider` | `openai` | LLM provider |
| `--model` | `gpt-5.2` | Model ID |
| `-r, --runs` | `1` | Runs for majority voting |
| `--budget-usd` | `0` | Cost limit |
| `-o, --output` | (none) | Save trajectory to JSON |

---

## 3. Environment Variables (.env)

Copy `.env.example` to `.env` and configure:

### Required for API Calls

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | For OpenAI | OpenAI API key |
| `ANTHROPIC_API_KEY` | For Anthropic | Anthropic API key |
| `GOOGLE_API_KEY` | Future | Google/Gemini API key (not implemented) |
| `HUGGINGFACE_TOKEN` | Optional | For gated HuggingFace datasets |

### Paper Parameters

| Variable | Default | Paper Value | Description |
|----------|---------|-------------|-------------|
| `MAX_ITERATIONS` | `20` | `20` | T parameter (max steps) |
| `WSI_LONG_SIDE_TARGET` | `1000` | `1000` | S parameter (crop target size) |
| `THUMBNAIL_SIZE` | `1024` | `1024` | Thumbnail long side |
| `PATCH_SIZE` | `224` | `224` | Patch size for baselines |
| `PATCH_COUNT` | `30` | `30` | Number of patches |
| `BOOTSTRAP_REPLICATES` | `1000` | `1000` | Bootstrap samples for CI |
| `OVERSAMPLING_BIAS` | `0.85` | `0.85` | Bias for larger crops |

### Per-Provider Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `IMAGE_SIZE_OPENAI` | `1000` | Image size for OpenAI calls |
| `IMAGE_SIZE_ANTHROPIC` | `500` | Image size for Anthropic (pricing) |
| `OPENAI_RPM` | `60` | Rate limit (requests/min) |
| `ANTHROPIC_RPM` | `60` | Rate limit (requests/min) |

### Logging

| Variable | Default | Options |
|----------|---------|---------|
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `LOG_FORMAT` | `console` | `console`, `json` |

### Prompt Overrides (Advanced)

For paper reproducibility, you can override system prompts:

| Variable | Description |
|----------|-------------|
| `GIANT_SYSTEM_PROMPT` | Global prompt override (inline) |
| `GIANT_SYSTEM_PROMPT_PATH` | Global prompt override (file path) |
| `GIANT_SYSTEM_PROMPT_OPENAI` | OpenAI-specific override |
| `GIANT_SYSTEM_PROMPT_OPENAI_PATH` | OpenAI-specific (file) |
| `GIANT_SYSTEM_PROMPT_ANTHROPIC` | Anthropic-specific override |
| `GIANT_SYSTEM_PROMPT_ANTHROPIC_PATH` | Anthropic-specific (file) |

Precedence: Provider-specific PATH > Provider-specific value > Global PATH > Global value

---

## 4. Model Registry

Approved models are enforced at runtime. See `docs/models/model-registry.md`.

| Provider | Default Model | Notes |
|----------|---------------|-------|
| OpenAI | `gpt-5.2` | 2025 frontier |
| Anthropic | `claude-sonnet-4-5-20250929` | 2025 frontier |
| Google | `gemini-3-pro-preview` | Provider not yet implemented |

---

## 5. AgentConfig (Programmatic)

When using GIANT as a library:

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

## 6. EvaluationConfig (Programmatic)

For batch evaluation:

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

## 7. Paper Parity Checklist

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

## 8. Common Gotchas

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

When `--budget-usd` is set, `--concurrency` is forced to 1 to prevent overruns.

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
