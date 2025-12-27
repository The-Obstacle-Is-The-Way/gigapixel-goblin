# Configuration Reference

This page documents all configuration options for GIANT.

## Environment Variables

### API Keys

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | For OpenAI | OpenAI API key (`sk-...`) |
| `ANTHROPIC_API_KEY` | For Anthropic | Anthropic API key (`sk-ant-...`) |
| `GOOGLE_API_KEY` | For Google | Google API key |

### Example `.env`

```bash
# .env - never commit this file!
OPENAI_API_KEY=sk-proj-abc123...
ANTHROPIC_API_KEY=sk-ant-api03-xyz789...
```

Load with:
```bash
source .env
```

---

## Agent Configuration

### `AgentConfig`

Configuration for `GIANTAgent` behavior.

```python
from giant.agent import AgentConfig

config = AgentConfig(
    max_steps=20,           # Maximum navigation steps (T in paper)
    max_retries=3,          # Max consecutive errors before termination
    budget_usd=None,        # Optional cost limit
    thumbnail_size=1024,    # Initial thumbnail size
    force_answer_retries=3, # Retries for forcing answer at max steps
    strict_font_check=False # Fail if axis fonts unavailable
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_steps` | `int` | `20` | Maximum navigation iterations |
| `max_retries` | `int` | `3` | Max consecutive errors |
| `budget_usd` | `float | None` | `None` | Cost limit (None = unlimited) |
| `thumbnail_size` | `int` | `1024` | Thumbnail max dimension |
| `force_answer_retries` | `int` | `3` | Answer enforcement retries |
| `strict_font_check` | `bool` | `False` | Require TrueType fonts |

### CLI Mapping

| CLI Option | AgentConfig Parameter |
|------------|----------------------|
| `--max-steps` / `-T` | `max_steps` |
| `--budget-usd` | `budget_usd` |
| `--strict-font-check` | `strict_font_check` |

---

## Evaluation Configuration

### `EvaluationConfig`

Configuration for benchmark runs.

```python
from giant.eval.runner import EvaluationConfig

config = EvaluationConfig(
    max_steps=20,
    max_concurrent=4,
    max_items=0,           # 0 = all items
    skip_missing_wsis=True,
    budget_usd=None,
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_steps` | `int` | `20` | Steps per item |
| `max_concurrent` | `int` | `4` | Concurrent API calls |
| `max_items` | `int` | `0` | Max items (0 = all) |
| `skip_missing_wsis` | `bool` | `True` | Skip missing files |
| `budget_usd` | `float | None` | `None` | Total cost limit |

---

## Provider Configuration

### Target Sizes

| Provider | Target Size | Rationale |
|----------|-------------|-----------|
| OpenAI | 1000px | Higher resolution |
| Anthropic | 500px | Cost-optimized |

### Model Defaults

| Provider | Default Model |
|----------|---------------|
| OpenAI | `gpt-5.2` |
| Anthropic | `claude-sonnet-4-5-20250929` |
| Google | `gemini-3-pro-preview` |

---

## Overlay Configuration

### `OverlayStyle`

Styling for axis guide overlays.

```python
from giant.geometry.overlay import OverlayStyle

style = OverlayStyle(
    line_color=(255, 0, 0),     # Red
    line_width=2,
    label_font_size=16,
    strict_font_check=False,
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `line_color` | `tuple[int, int, int]` | `(255, 0, 0)` | RGB color |
| `line_width` | `int` | `2` | Line thickness |
| `label_font_size` | `int` | `16` | Font size |
| `strict_font_check` | `bool` | `False` | Require TrueType |

---

## Logging Configuration

### Verbosity Levels

| Level | CLI | Python |
|-------|-----|--------|
| Warning | (default) | `logging.WARNING` |
| Info | `-v` | `logging.INFO` |
| Debug | `-vv` | `logging.DEBUG` |

### Programmatic Setup

```python
from giant.utils.logging import configure_logging

configure_logging(level="DEBUG")
```

---

## Directory Structure

### Default Paths

| Purpose | Default Path | CLI Override |
|---------|--------------|--------------|
| WSI root | `data/wsi/` | `--wsi-root` |
| Benchmark CSV | `data/multipathqa/MultiPathQA.csv` | `--csv-path` |
| Results | `results/` | `--output-dir` |
| Checkpoints | `results/checkpoints/` | (auto) |
| Trajectories | `results/trajectories/` | (auto) |

### WSI Subdirectories

```
data/wsi/
├── tcga/      # TCGA slides (all 3 benchmarks)
├── gtex/      # GTEx slides
└── panda/     # PANDA slides
```

---

## Model Registry

### Approved Models

Only these models are allowed at runtime:

```python
APPROVED_MODELS = frozenset({
    "gpt-5.2",
    "claude-sonnet-4-5-20250929",
    "gemini-3-pro-preview",
})
```

### Validation

```python
from giant.llm.model_registry import validate_model_id

validate_model_id("gpt-5.2")  # OK
validate_model_id("gpt-4o")   # Raises ValueError
```

See [Model Registry](../models/model-registry.md) for details.

---

## Pricing

### Cost Calculation

Costs are calculated using pricing tables:

```python
from giant.llm.pricing import calculate_cost

cost = calculate_cost(
    model="gpt-5.2",
    prompt_tokens=1000,
    completion_tokens=500,
)
```

### Current Pricing (per 1M tokens)

| Model | Input | Output |
|-------|-------|--------|
| gpt-5.2 | $2.50 | $10.00 |
| claude-sonnet-4-5-20250929 | $3.00 | $15.00 |

---

## See Also

- [CLI Reference](cli.md)
- [Model Registry](../models/model-registry.md)
- [Architecture](../concepts/architecture.md)
