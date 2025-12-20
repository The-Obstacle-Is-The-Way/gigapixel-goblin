# BUG-026: Model ID Configuration Scattered Across Codebase

## Severity: P3 (Code Quality / Maintainability)

## Status: Fixed

## Description

Changing the default Anthropic model from `claude-opus-4-5-20251101` to `claude-sonnet-4-5-20250929` required modifying **17 files**. This is an anti-pattern indicating scattered configuration that should be centralized.

## Evidence

Files touched for a single model change:

**Core Code (4 files):**
1. `src/giant/llm/model_registry.py` - ANTHROPIC_MODELS set
2. `src/giant/llm/pricing.py` - pricing table
3. `src/giant/llm/anthropic_client.py` - default model attribute
4. `src/giant/llm/__init__.py` - fallback in factory function

**Documentation (5 files):**
5. `docs/models/MODEL_REGISTRY.md` - SSOT documentation
6. `CLAUDE.md` - project guidance
7. `docs/specs/spec-06-llm-provider.md` - spec examples
8. `docs/validation/E2E-VALIDATION-2025-12-20.md` - validation report
9. `docs/bugs/archive/BUG-014-env-secrets-management.md` - archived bug

**Tests (8 files):**
10. `tests/unit/llm/test_model_registry.py`
11. `tests/unit/llm/test_pricing.py`
12. `tests/unit/llm/test_anthropic.py`
13. `tests/unit/llm/test_factory.py`
14. `tests/unit/llm/test_openai.py`
15. `tests/unit/cli/test_runners.py`
16. `tests/integration/llm/test_p0_critical.py`
17. `tests/integration/llm/test_p1_high_priority.py`

## Root Cause Analysis

### What's Correct

The `model_registry.py` file correctly serves as the **validator** for which models are allowed. This is good architecture.

### What's Wrong

1. **Default model defined in multiple places:**
   - `anthropic_client.py:121` - `model: str = "claude-sonnet-4-5-20250929"`
   - `__init__.py:104` - `chosen_model = model or "claude-sonnet-4-5-20250929"`

2. **Tests hardcode model IDs** instead of using centralized fixtures or constants

3. **No single source of truth for defaults** - The registry validates, but doesn't define defaults

## Fix Implemented

### 1. Centralize defaults in `model_registry.py`

```python
# model_registry.py

# Approved models (validation)
ANTHROPIC_MODELS: frozenset[str] = frozenset({"claude-sonnet-4-5-20250929"})
OPENAI_MODELS: frozenset[str] = frozenset({"gpt-5.2"})

# Default models (configuration SSOT)
DEFAULT_ANTHROPIC_MODEL: str = "claude-sonnet-4-5-20250929"
DEFAULT_OPENAI_MODEL: str = "gpt-5.2"
DEFAULT_GOOGLE_MODEL: str = "gemini-3-pro-preview"
```

### 2. Use defaults everywhere in code

```python
# anthropic_client.py
from giant.llm.model_registry import DEFAULT_ANTHROPIC_MODEL

@dataclass
class AnthropicProvider:
    model: str = DEFAULT_ANTHROPIC_MODEL  # Single import, no hardcoded string
```

```python
# __init__.py
from giant.llm.model_registry import DEFAULT_ANTHROPIC_MODEL, DEFAULT_OPENAI_MODEL

def create_provider(provider: str, model: str | None = None):
    if provider == "anthropic":
        chosen_model = model or DEFAULT_ANTHROPIC_MODEL  # Single import
```

### 3. Remove hardcoded IDs from tests

Tests import `DEFAULT_ANTHROPIC_MODEL` / `DEFAULT_OPENAI_MODEL` directly so a future
default-model update does not require editing test expectations that only assert
"default == default".

### 4. Result

After refactoring, a model change would only require updating:

1. `model_registry.py` - The SSOT
2. `pricing.py` - Pricing table (could also be data-driven)
3. Documentation files (unavoidable for human-readable docs)

This reduces “string scatter” changes in tests to ~0 (pricing expectation changes
may still be needed if the new default model has different costs).

## Impact Assessment

| Current | After Fix |
|---------|-----------|
| 17 files to change | ~4 files to change |
| Hardcoded strings everywhere | Single import from registry |
| Easy to miss a file | Impossible to have inconsistency |
| Tests break if constant missed | Tests use fixtures automatically |

## Priority Justification

P3 because:
- Not a functional bug (system works correctly)
- Not a security issue
- Is a maintainability/DX issue that increases risk of future bugs
- Would have prevented the near-miss where wrong model ID was almost used

## References

- Commit that triggered this observation: `7ccb026` (17 files changed)
- Related: BUG-014 (env secrets management) - similar centralization issue
