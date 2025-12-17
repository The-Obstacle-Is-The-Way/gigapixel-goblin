# BUG-008: API Keys Are Silently None - No Validation

## Severity: P1 (High Priority)

## Status: Open

## Description

API keys in `config.py` default to `None` with no validation that they're set before use. When LLM calls are made, the system will fail with confusing errors instead of failing fast with a clear message.

### Current Code

```python
# src/giant/config.py:19-22
class Settings(BaseSettings):
    # API Keys
    OPENAI_API_KEY: str | None = None      # ← Silently None
    ANTHROPIC_API_KEY: str | None = None   # ← Silently None
    HUGGINGFACE_TOKEN: str | None = None   # ← Silently None
```

### What Happens When None

When Spec-06+ implements the LLM agent loop:

```python
# Future code (Spec-06)
from giant.config import settings

client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)  # api_key=None
response = client.chat.completions.create(...)  # Cryptic auth error
```

The user sees:
```
openai.AuthenticationError: No API key provided.
```

Instead of:
```
giant.ConfigError: OPENAI_API_KEY not set. Set it in .env or environment.
```

### Expected Behavior

**Option A: Fail Fast at Startup**
```python
@field_validator("OPENAI_API_KEY")
@classmethod
def validate_api_key(cls, v: str | None) -> str | None:
    # Only validate when running LLM commands
    return v

def require_openai_key(self) -> str:
    """Get OpenAI key, raising clear error if not set."""
    if self.OPENAI_API_KEY is None:
        raise ConfigError(
            "OPENAI_API_KEY not configured. "
            "Set it in .env file or OPENAI_API_KEY environment variable."
        )
    return self.OPENAI_API_KEY
```

**Option B: Validate at Import (stricter)**
```python
def __init__(self, **kwargs):
    super().__init__(**kwargs)
    # Warn about missing keys at startup
    if self.OPENAI_API_KEY is None:
        logger.warning("OPENAI_API_KEY not set - LLM features will fail")
```

### Similar Issues

- `HUGGINGFACE_TOKEN` in `download.py:38`: `token=settings.HUGGINGFACE_TOKEN or None`
  - This silently downloads without auth if token is not set
  - Some HuggingFace repos require auth and will fail cryptically

### Code Location

- `src/giant/config.py:19-22` - Nullable API keys with no validation
- `src/giant/data/download.py:38` - Silently uses None token

### Impact

- Confusing errors for users who forgot to set API keys
- No clear guidance on what to set and where
- Production debugging nightmare

### Testing Required

- Unit test: Verify clear error when API key needed but missing
- Unit test: Verify warning logged when keys not set at startup
