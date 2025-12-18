# GIANT Model Registry

> **SSOT for LLM model identifiers used in GIANT**
>
> This diverges from the original paper to use current frontier models (Dec 2025).

## Approved Models

| Provider   | Model Name         | API Model ID                    | Context   | Max Output | Notes                          |
|------------|--------------------|---------------------------------|-----------|------------|--------------------------------|
| Anthropic  | Claude Opus 4.5    | `claude-opus-4-5-20251101`      | 200K      | 64K        | Best for coding & agents       |
| Google     | Gemini 3.0 Pro     | `gemini-3-pro-preview`          | 1M        | -          | Advanced reasoning, multimodal |
| OpenAI     | GPT-5.2 Pro        | `gpt-5.2-pro-2025-12-11`        | 400K      | 128K       | Flagship for agentic tasks     |

## Pricing (USD per 1M tokens)

| Model                        | Input    | Output   | Image Cost                    |
|------------------------------|----------|----------|-------------------------------|
| `claude-opus-4-5-20251101`   | $5.00    | $25.00   | Pixel-based (~$0.48/1K px)    |
| `gemini-3-pro-preview`       | $2.00    | $12.00   | Included in token count       |
| `gpt-5.2-pro-2025-12-11`     | $21.00   | $168.00  | Flat-rate per image           |

> **Note:** GPT-5.2 Pro is expensive but designed for complex agentic tasks.
> For cost-sensitive workloads, consider GPT-5.2 standard ($1.75/$14.00).

## Why These Models?

1. **Claude Opus 4.5** - 80.9% SWE-bench Verified, 66.3% OSWorld. Best computer-use model.
2. **Gemini 3.0 Pro** - 1M context window, native multimodal, `thinking_level` control.
3. **GPT-5.2 Pro** - 400K context, 128K output, designed for long-running agents.

## Code Usage

```python
from giant.llm import create_provider

# Anthropic
provider = create_provider("anthropic", model="claude-opus-4-5-20251101")

# Google (requires adding GeminiProvider)
provider = create_provider("google", model="gemini-3-pro-preview")

# OpenAI
provider = create_provider("openai", model="gpt-5.2-pro-2025-12-11")
```

## Sources

- [Anthropic Claude Opus 4.5](https://www.anthropic.com/claude/opus)
- [Google Gemini 3 Pro](https://ai.google.dev/gemini-api/docs/gemini-3)
- [OpenAI GPT-5.2](https://platform.openai.com/docs/models/gpt-5.2)
