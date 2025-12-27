# GIANT Model Registry

> **Single Source of Truth for LLM model identifiers used in GIANT**
>
> This diverges from the original paper to use current frontier models (Dec 2025).

## Approved Models

| Provider   | Model Name         | API Model ID                    | Context   | Max Output | Notes                           |
|------------|--------------------|---------------------------------|-----------|------------|---------------------------------|
| Anthropic  | Claude Sonnet 4.5  | `claude-sonnet-4-5-20250929`    | 200K      | 64K        | Best for coding & agents        |
| Google     | Gemini 3.0 Pro     | `gemini-3-pro-preview`          | 1M        | 64K        | Advanced reasoning, multimodal  |
| OpenAI     | GPT-5.2            | `gpt-5.2`                       | 400K      | 128K       | Cost-effective frontier model   |

## Pricing (USD per 1M tokens)

| Model                        | Input    | Output   | Image Cost                    |
|------------------------------|----------|----------|-------------------------------|
| `claude-sonnet-4-5-20250929` | $3.00    | $15.00   | Pixel-based (~$0.48/1K px)    |
| `gemini-3-pro-preview`       | $2.00    | $12.00   | Included in token count       |
| `gpt-5.2`                    | $1.75    | $14.00   | Flat-rate per image           |

## Why These Models?

1. **Claude Sonnet 4.5** - 77.2% SWE-bench Verified, 61.4% OSWorld. Best coding model.
2. **Gemini 3.0 Pro** - 1M context window, native multimodal, `thinking_level` control.
3. **GPT-5.2** - 400K context, 128K output, cost-effective at $1.75/$14 per 1M tokens.

## Code Usage

```python
from giant.llm import create_provider

# Anthropic
provider = create_provider("anthropic", model="claude-sonnet-4-5-20250929")

# Google (requires adding GeminiProvider)
provider = create_provider("google", model="gemini-3-pro-preview")

# OpenAI
provider = create_provider("openai", model="gpt-5.2")
```

## Sources

- [Anthropic Claude Sonnet 4.5](https://www.anthropic.com/claude/sonnet)
- [Google Gemini 3 Pro](https://ai.google.dev/gemini-api/docs/gemini-3)
- [OpenAI GPT-5.2](https://platform.openai.com/docs/models/gpt-5.2)
