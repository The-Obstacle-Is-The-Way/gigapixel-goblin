# Configuring Providers

This guide covers setting up LLM providers for GIANT.

## Overview

GIANT currently supports these LLM providers:

| Provider | Model | Status |
|----------|-------|--------|
| OpenAI | `gpt-5.2` | Default |
| Anthropic | `claude-sonnet-4-5-20250929` | Supported |

`gemini-3-pro-preview` is present in the model registry for future work, but the Google/Gemini provider is not implemented in the CLI yet.

## API Key Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
# .env
OPENAI_API_KEY=sk-proj-...
ANTHROPIC_API_KEY=sk-ant-api03-...
```

Load before running:

```bash
source .env
giant run slide.svs -q "Question?"
```

### Shell Export

Alternatively, export directly:

```bash
export OPENAI_API_KEY=sk-proj-...
giant run slide.svs -q "Question?"
```

### Security Notes

1. **Never commit `.env` files** - Add to `.gitignore`
2. **Avoid placeholder values** - Keys containing `your-key` or `changeme` are treated as not configured
3. **Use environment-specific keys** - Separate keys for dev/test/prod
4. **Rotate compromised keys** - If exposed, regenerate immediately

## OpenAI Setup

### Getting an API Key

1. Go to [OpenAI Platform](https://platform.openai.com/)
2. Create an account or sign in
3. Navigate to API Keys
4. Create a new secret key
5. Copy and save securely

### Configuration

```bash
# .env
OPENAI_API_KEY=sk-proj-abc123...
```

### Usage

```bash
giant run slide.svs -q "Question?" --provider openai --model gpt-5.2
```

### Pricing

| Model | Input (per 1M) | Output (per 1M) |
|-------|----------------|-----------------|
| gpt-5.2 | $1.75 | $14.00 |

### Target Image Size

OpenAI provider uses **1000px** target size for higher resolution analysis.

## Anthropic Setup

### Getting an API Key

1. Go to [Anthropic Console](https://console.anthropic.com/)
2. Create an account or sign in
3. Navigate to API Keys
4. Create a new key
5. Copy and save securely

### Configuration

```bash
# .env
ANTHROPIC_API_KEY=sk-ant-api03-abc123...
```

### Usage

```bash
giant run slide.svs -q "Question?" --provider anthropic --model claude-sonnet-4-5-20250929
```

### Pricing

| Model | Input (per 1M) | Output (per 1M) |
|-------|----------------|-----------------|
| claude-sonnet-4-5-20250929 | $3.00 | $15.00 |

### Target Image Size

Anthropic provider uses **500px** target size (cost-optimized).

## Model Registry

Only approved models are allowed. This ensures:

1. **Consistency** - Reproducible results
2. **Cost control** - Known pricing
3. **Compatibility** - Tested integration

### Approved Models

```python
APPROVED_MODELS = {
    "gpt-5.2",                      # OpenAI
    "claude-sonnet-4-5-20250929",   # Anthropic
    "gemini-3-pro-preview",         # Reserved (Google/Gemini provider not yet implemented)
}
```

### Validation

Invalid models are rejected at runtime:

```bash
giant run slide.svs -q "?" --model gpt-4o
# Error: Model 'gpt-4o' is not approved. Allowed for openai approved models: gpt-5.2. See docs/models/model-registry.md.
```

See [Model Registry](../models/model-registry.md) for the full list.

## Provider Comparison

| Feature | OpenAI | Anthropic |
|---------|--------|-----------|
| Default model | gpt-5.2 | claude-sonnet-4-5-20250929 |
| Target size | 1000px | 500px |
| Structured output | JSON schema via `responses.create` | Tool use via `submit_step` |
| Image cost model | Flat per image | Pixel-based |

## Troubleshooting

### "API key not set"

```
Error: OpenAI API key not configured. Set it in .env file or OPENAI_API_KEY environment variable.
```

**Fix:** Ensure the key is exported:
```bash
source .env
echo $OPENAI_API_KEY  # Should print your key
```

### "Invalid API key"

```
Error: openai.AuthenticationError: Invalid API key
```

**Fix:** Check your key is correct and has not expired.

### "Placeholder key treated as not configured"

If your key contains obvious placeholder strings (e.g., `your-key`, `changeme`), GIANT treats it as missing and raises the same configuration error as an unset key.

### "Model not approved"

```
Error: Model 'gpt-4o' not approved
```

**Fix:** Use an approved model from the registry.

### Rate Limits

If you hit rate limits:

1. Reduce concurrency: `--concurrency 1`
2. Add delays between requests (not currently configurable)
3. Upgrade your API tier

## Programmatic Usage

```python
from giant.llm import create_provider

# OpenAI
provider = create_provider("openai", model="gpt-5.2")

# Anthropic
provider = create_provider("anthropic", model="claude-sonnet-4-5-20250929")

# Use with agent
from giant.agent import GIANTAgent, AgentConfig

agent = GIANTAgent(
    wsi_path="slide.svs",
    question="What tissue is this?",
    llm_provider=provider,
    config=AgentConfig(max_steps=10),
)
result = await agent.run()
```

## Next Steps

- [Model Registry](../models/model-registry.md) - All approved models
- [Running Inference](running-inference.md) - Use configured provider
- [LLM Integration](../concepts/llm-integration.md) - Technical details
