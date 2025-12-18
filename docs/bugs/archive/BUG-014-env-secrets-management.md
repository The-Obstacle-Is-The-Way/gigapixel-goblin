# BUG-014: Environment Secrets Management Gap

## Severity: P1 (High Priority) - Security & Configuration Integrity

## Status: Closed (Fixed)

## Summary

The project has a `.env.example` template but it's incomplete, and there's no documentation explaining:
1. Which API keys are required vs optional
2. How tests pick up API keys (shell env vs `.env` file)
3. What Google/Gemini integration status is
4. How to safely run live tests without accidentally hitting APIs

This caused confusion when a live Anthropic test ran unexpectedly because `ANTHROPIC_API_KEY` was exported in the user's shell environment.

---

## Current State Analysis

### 1. `.env.example` Is Incomplete

```bash
# Current .env.example (only 4 lines)
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
HUGGINGFACE_TOKEN=
LOG_LEVEL=INFO
```

**Missing:**
- `GOOGLE_API_KEY` - Gemini is in the model registry but no config support
- Documentation comments explaining each key
- Guidance on which keys are required for what

### 2. Model Registry vs Config Mismatch

| Provider | In Model Registry | In Config | Provider Client |
|----------|-------------------|-----------|-----------------|
| OpenAI | `gpt-5.2` | `OPENAI_API_KEY` | `openai_client.py` |
| Anthropic | `claude-opus-4-5-20251101` | `ANTHROPIC_API_KEY` | `anthropic_client.py` |
| Google | `gemini-3-pro-preview` | **MISSING** | **MISSING** |

**Issue:** Google/Gemini models are in `model_registry.py` and `pricing.py` but:
- No `GOOGLE_API_KEY` in `config.py`
- No `require_google_key()` method
- No `google_client.py` provider implementation
- This is scaffolding for future work, but it's misleading

### 3. HuggingFace Token Usage

```python
# src/giant/data/download.py:36-41
token = settings.HUGGINGFACE_TOKEN
if token is None:
    logger.debug(
        "HUGGINGFACE_TOKEN not set, using anonymous access. "
        "Set token in .env for private/gated datasets."
    )
```

**Status:** Optional. Only needed for gated/private datasets. MultiPathQA is public.

### 4. Test Environment Behavior

The live tests use `os.getenv()` which reads from:
1. Shell environment variables (`~/.zshrc`, `~/.bashrc`, etc.)
2. `.env` file (via pydantic-settings)

**Problem:** If you have `ANTHROPIC_API_KEY` exported in your shell (for other projects), the live tests run automatically and hit real APIs with real costs.

```python
# tests/integration/llm/test_p0_critical.py:1117-1119
@pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),  # Reads from shell OR .env
    reason="ANTHROPIC_API_KEY not set",
)
```

---

## What We Need

### A. Complete `.env.example`

```bash
# =============================================================================
# GIANT WSI + LLM Pipeline - Environment Configuration
# =============================================================================
# Copy to .env and fill in values. The .env file is gitignored.
#
# REQUIRED FOR LIVE TESTS:
#   - OPENAI_API_KEY: Required for OpenAI live tests
#   - ANTHROPIC_API_KEY: Required for Anthropic live tests
#
# OPTIONAL:
#   - HUGGINGFACE_TOKEN: Only for gated/private datasets (MultiPathQA is public)
#   - GOOGLE_API_KEY: Reserved for future Gemini integration (not implemented)
#
# =============================================================================

# --- LLM Provider API Keys ---
# Get from: https://platform.openai.com/api-keys
OPENAI_API_KEY=

# Get from: https://console.anthropic.com/settings/keys
ANTHROPIC_API_KEY=

# Reserved for future Gemini integration (Spec-XX)
# GOOGLE_API_KEY=

# --- Data Access ---
# Get from: https://huggingface.co/settings/tokens
# Optional - only needed for gated/private HuggingFace datasets
HUGGINGFACE_TOKEN=

# --- Logging ---
# Options: DEBUG, INFO, WARNING, ERROR
LOG_LEVEL=INFO
# Options: console, json
LOG_FORMAT=console
```

### B. Config.py Updates Needed

1. Add `GOOGLE_API_KEY` placeholder (commented as future)
2. OR remove Google from model_registry until implemented
3. Document the precedence: shell env → .env file

### C. Test Documentation

Update spec-08.5 to clearly explain:
```markdown
## Running Tests

### Mock Tests (Default, No API Keys Needed)
```bash
uv run pytest tests/integration/llm/ -m mock
```

### Live Tests (Requires API Keys in .env)
```bash
# Create .env from template
cp .env.example .env
# Edit .env with your keys

# Run live tests (costs money!)
uv run pytest tests/integration/llm/ -m live -v
```

### WARNING: Shell Environment
If you have API keys exported in your shell (`~/.zshrc`), live tests
will run automatically. Use `-m mock` to avoid this.
```

---

## Spec Analysis - Gemini Intent

### What the Specs Say

| Document | Gemini Status |
|----------|---------------|
| `spec-06-llm-provider.md` | Gemini in pricing example, NOT in acceptance criteria |
| `spec-08.5-llm-integration-checkpoint.md` | **P4-1: "Gemini provider - Not in current spec - Document as future work"** |
| `docs/models/MODEL_REGISTRY.md` | Gemini listed as approved model with pricing |
| `src/giant/llm/model_registry.py` | `GOOGLE_MODELS` defined with `gemini-3-pro-preview` |
| `src/giant/llm/pricing.py` | Gemini pricing defined |
| `src/giant/config.py` | **NO GOOGLE_API_KEY** |
| `src/giant/llm/` | **NO google_client.py** |

### Conclusion

Gemini was **intentionally planned** for the future (P4 priority) but the scaffolding is incomplete:
- Model registry and pricing are ready
- Config and provider implementation are missing

---

## Decision Points

### Q1: What to do about Google/Gemini?

**Options:**
1. **Remove from model_registry** - Clean up scaffolding until we implement it
2. **Keep scaffolding, complete config** - Add `GOOGLE_API_KEY` to config, keep provider as future
3. **Implement now** - Add `google_client.py` (scope creep for current checkpoint)

**Recommendation:** Option 2 - Complete the config scaffolding, document provider as P4 future work

**Why:** The model_registry and pricing are already there. Adding `GOOGLE_API_KEY` to config.py makes it consistent and ready for when we implement the provider. This is low-risk, high-clarity.

### Q2: Should tests ONLY read from `.env`, not shell?

**Options:**
1. **Keep current behavior** - Reads shell env (standard Python behavior)
2. **Force .env only** - Override with explicit `_env_file` loading in tests
3. **Document clearly** - Warn users about shell env in test docs

**Recommendation:** Option 3 - Document clearly, don't fight Python conventions

---

## Implementation Checklist

- [x] Update `.env.example` with comprehensive comments
- [x] Update `docs/specs/spec-08.5-llm-integration-checkpoint.md` with test warnings
- [x] Decide on Google/Gemini status and document → **Decision: Keep scaffolding, complete config**
- [x] Add `GOOGLE_API_KEY` to `config.py` with `require_google_key()` method
- [x] Update `spec-06-llm-provider.md` to note Gemini as P4 future work
- [x] Consider: Should model_registry reject Google until implemented? → **No, scaffolding is fine**
- [x] Fix test skipif to detect keys from `.env` file (not just shell env)
- [x] Fix Anthropic JSON string parsing for nested action field
- [x] Fix OpenAI schema to not use `oneOf` (use flattened schema with nulls)

---

## Code Locations

| File | Issue |
|------|-------|
| `.env.example` | Incomplete, no comments |
| `src/giant/config.py` | Missing GOOGLE_API_KEY |
| `src/giant/llm/model_registry.py` | Has Google but no provider |
| `src/giant/llm/pricing.py` | Has Gemini pricing but unused |
| `tests/integration/llm/test_p0_critical.py` | Uses `os.getenv()` (shell + .env) |
| `docs/specs/spec-08.5-llm-integration-checkpoint.md` | Needs clearer test docs |

---

## Risk If Not Fixed

1. **Cost Surprise:** Users with shell-exported keys run live tests unknowingly
2. **Confusion:** Google in registry but can't actually use it
3. **Onboarding Friction:** New devs don't know which keys are needed
4. **Security:** No guidance on key management best practices
