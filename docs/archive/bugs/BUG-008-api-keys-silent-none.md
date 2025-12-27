# BUG-008: API Keys Are Silently None - No Validation

## Severity: P3 (Low Priority) - DevEx / Future Spec-06

## Status: Fixed - require_*_key() methods added

## Description

API keys in `config.py` default to `None`. This is a reasonable default (not every command needs every key), but once LLM provider implementations (Spec-06) or CLI commands (Spec-12) require a key, we should raise a clear, GIANT-specific error at the **use site**.

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

Today, this is not a runtime bug because LLM providers are not implemented yet. The future improvement is to raise something like:

```
giant.ConfigError: OPENAI_API_KEY not set. Set it in .env or environment.
```

### Expected Behavior

**Option A: Validate at the provider boundary (recommended)**
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

**Option B: Warn at startup (optional)**
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

- Minor DevEx friction: users may hit provider-SDK auth errors instead of GIANT’s own actionable message.
- Not a production correctness issue as long as we validate before making paid API calls.

### Testing Required

- Unit test: Verify clear error when API key needed but missing
- Unit test: Verify warning logged when keys not set at startup

## Resolution

**Implemented**: Option A (validate at the provider boundary)

Added `ConfigError` exception and `require_*_key()` methods to `Settings` class:

### New Code

```python
# src/giant/config.py

class ConfigError(Exception):
    """Raised when required configuration is missing or invalid."""
    def __init__(self, key_name: str, env_var: str) -> None:
        self.key_name = key_name
        self.env_var = env_var
        message = (
            f"{key_name} not configured. "
            f"Set it in .env file or {env_var} environment variable."
        )
        super().__init__(message)

class Settings(BaseSettings):
    # ... existing settings ...

    def require_openai_key(self) -> str:
        """Get OpenAI API key, raising ConfigError if not set."""
        if self.OPENAI_API_KEY is None:
            raise ConfigError("OpenAI API key", "OPENAI_API_KEY")
        return self.OPENAI_API_KEY

    def require_anthropic_key(self) -> str:
        """Get Anthropic API key, raising ConfigError if not set."""
        if self.ANTHROPIC_API_KEY is None:
            raise ConfigError("Anthropic API key", "ANTHROPIC_API_KEY")
        return self.ANTHROPIC_API_KEY

    def require_huggingface_token(self) -> str:
        """Get HuggingFace token, raising ConfigError if not set."""
        if self.HUGGINGFACE_TOKEN is None:
            raise ConfigError("HuggingFace token", "HUGGINGFACE_TOKEN")
        return self.HUGGINGFACE_TOKEN
```

### Tests Added

`tests/unit/test_config.py`:
- `TestConfigError` - message format, attributes
- `TestRequireMethods` - 6 tests covering when keys are set/missing

### Usage (Spec-06+)

```python
from giant.config import settings

# Before making API calls:
api_key = settings.require_openai_key()  # Raises ConfigError if not set
client = openai.OpenAI(api_key=api_key)
```
