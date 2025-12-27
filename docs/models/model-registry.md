# GIANT Model Registry

> **Single Source of Truth for LLM model identifiers used in GIANT**
>
> This diverges from the original paper to use current frontier models (Dec 2025).

## Approved Models

These are the only model IDs allowed by `src/giant/llm/model_registry.py`.

| Provider | API Model ID | Runtime Support | Notes |
|----------|--------------|-----------------|-------|
| OpenAI | `gpt-5.2` | Supported | Default OpenAI model |
| Anthropic | `claude-sonnet-4-5-20250929` | Supported | Default Anthropic model |
| Google | `gemini-3-pro-preview` | Planned | Model ID is reserved; Google/Gemini provider is not implemented yet |

## Pricing (USD per 1M tokens)

| Model                        | Input    | Output   | Image Cost                    |
|------------------------------|----------|----------|-------------------------------|
| `claude-sonnet-4-5-20250929` | $3.00    | $15.00   | Pixel-based (~$0.00048/1K px) |
| `gemini-3-pro-preview`       | $2.00    | $12.00   | Included in token count       |
| `gpt-5.2`                    | $1.75    | $14.00   | Flat-rate per image ($0.00255/image) |

Notes:
- The Anthropic image cost in code is `$0.00048 / 1K pixels` (i.e., `$0.48 / 1M pixels`).
- Pricing and image-cost formulas are implemented in `src/giant/llm/pricing.py`.

## Why These IDs?

GIANT pins model IDs for reproducibility and to ensure pricing is known. If you need to update pricing or supported models, update `docs/models/model-registry.md` and `src/giant/llm/pricing.py`, and keep `src/giant/llm/model_registry.py` aligned.

## Code Usage

```python
from giant.llm import create_provider
from giant.llm.model_registry import validate_model_id

# OpenAI
provider = create_provider("openai", model="gpt-5.2")

# Anthropic
provider = create_provider("anthropic", model="claude-sonnet-4-5-20250929")

# Google/Gemini (reserved model ID; provider not implemented)
validate_model_id("gemini-3-pro-preview", provider="google")  # OK
```

## Sources

- [Anthropic Claude Sonnet 4.5](https://www.anthropic.com/claude/sonnet)
- [Google Gemini 3 Pro](https://ai.google.dev/gemini-api/docs/gemini-3)
- [OpenAI GPT-5.2](https://platform.openai.com/docs/models/gpt-5.2)
