# Technical Debt Spec: P2 Medium Priority Items

**Priority:** P2 (Medium)
**Total Items:** 5 remaining
**Effort:** Small to Medium each
**Status:** DEFERRED - Design decisions needed

---

## Overview

These are medium-priority code quality issues that should be addressed before the next major release. Each requires either a design decision or codebase-wide changes.

| ID | Issue | Effort | Blocker |
|----|-------|--------|---------|
| P2-1 | Inconsistent frozen dataclass usage | Small | Policy decision needed |
| P2-2 | Test fixture uses old API structure | Small | Low impact |
| P2-4 | Inconsistent logging patterns | Medium | Cross-cutting change |
| P2-7 | Hardcoded retry parameters | Small | Design decision needed |
| P2-8 | Inconsistent `strict=True` in zip() | Small | Codebase audit needed |

---

## P2-1: Inconsistent Frozen Dataclass Usage

### Problem

Some dataclasses use `frozen=True`, others don't. No documented policy.

### Current State

```python
# FROZEN (immutable)
@dataclass(frozen=True)
class ExtractedAnswer:        # answer_extraction.py
class BootstrapResult:        # metrics.py
class Region:                 # primitives.py

# NOT FROZEN (mutable)
@dataclass
class OverlayStyle:           # overlay.py (has __post_init__)
class BenchmarkItem:          # schemas.py
class BenchmarkResult:        # schemas.py
```

### Proposed Policy

**Rule:** Use `frozen=True` for value objects; use mutable for objects that need post-initialization.

| Category | Frozen | Examples |
|----------|--------|----------|
| Value objects (coordinates, results) | Yes | `Region`, `Point`, `Size`, `ExtractedAnswer` |
| Configuration objects | No | `OverlayStyle`, `EvaluationConfig` |
| Data transfer objects | No | `BenchmarkItem`, `BenchmarkResult` |

### Implementation

1. Document policy in `CONTRIBUTING.md`
2. Audit all dataclasses for consistency
3. Add comments explaining why each is frozen or not

### Files Affected

```
src/giant/geometry/primitives.py
src/giant/geometry/overlay.py
src/giant/data/schemas.py
src/giant/eval/answer_extraction.py
src/giant/eval/metrics.py
src/giant/llm/protocol.py
```

---

## P2-2: Test Fixture Uses Old API Response Structure

### Problem

`tests/conftest.py:40-71` has `mock_api_responses` fixture using Chat Completions API format, but production code uses Responses API.

### Current State

```python
# conftest.py - Uses old format
@pytest.fixture
def mock_api_responses():
    return {
        "choices": [{"message": {"content": "..."}}]  # Chat Completions format
    }
```

### Investigation Needed

1. Search for usages of `mock_api_responses` fixture
2. Determine if it's actively used or dead code
3. If used, update to Responses API format
4. If unused, remove entirely

### Commands to Run

```bash
# Find usages
grep -r "mock_api_responses" tests/

# Check if tests still pass without it
pytest tests/unit -x
```

### Implementation

If fixture is used:
```python
@pytest.fixture
def mock_api_responses():
    return {
        "output": [{"type": "message", "content": [...]}]  # Responses API format
    }
```

If unused: Delete the fixture.

---

## P2-4: Inconsistent Logging Patterns

### Problem

Mixed logging styles across the codebase:

```python
# Style 1: Structured (preferred)
logger.info("Processing item", item_id=item.id, wsi=str(wsi_path))

# Style 2: Format strings
logger.info("Processing item %s from %s", item_id, wsi_path)

# Style 3: f-strings (worst - evaluated even when logging disabled)
logger.info(f"Processing item {item_id} from {wsi_path}")
```

### Proposed Standard

Use **structured logging** (Style 1) with `structlog` integration:

```python
import structlog

logger = structlog.get_logger(__name__)

# All log calls use keyword arguments
logger.info("item.processing.started", item_id=item.id, wsi_path=str(wsi_path))
logger.error("item.processing.failed", item_id=item.id, error=str(e))
```

### Benefits

- Machine-parseable logs
- Consistent format across codebase
- Easy to filter/search in production
- No string formatting overhead

### Files Affected (Major)

```
src/giant/agent/runner.py      # 15+ log calls
src/giant/eval/runner.py       # 20+ log calls
src/giant/llm/openai_client.py # 5+ log calls
src/giant/llm/anthropic_client.py # 5+ log calls
src/giant/core/crop_engine.py  # 3+ log calls
```

### Implementation Steps

1. Add `structlog` to dependencies
2. Create logging configuration in `src/giant/logging.py`
3. Update all log calls file-by-file
4. Add log event naming convention to `CONTRIBUTING.md`

### Effort Estimate

- Setup: 1 hour
- Migration: 2-4 hours (many files)
- Testing: 1 hour

---

## P2-7: Hardcoded Retry Parameters

### Problem

Retry logic uses hardcoded values instead of configurable settings:

```python
# openai_client.py:207-212
@retry(
    wait=wait_random_exponential(min=1, max=60),
    stop=stop_after_attempt(6),
    retry=retry_if_exception_type((RateLimitError, APIConnectionError)),
)

# anthropic_client.py:195-200 (same values)
@retry(
    wait=wait_random_exponential(min=1, max=60),
    stop=stop_after_attempt(6),
    retry=retry_if_exception_type((RateLimitError, APIConnectionError)),
)
```

### Design Decision Needed

**Option A: Add to Settings (Configurable)**

```python
# config.py
class Settings(BaseSettings):
    RETRY_MIN_WAIT: int = 1
    RETRY_MAX_WAIT: int = 60
    RETRY_MAX_ATTEMPTS: int = 6
```

Pros: Users can tune for their use case
Cons: More configuration surface

**Option B: Document as Fixed (No Change)**

Add comment explaining why values are fixed:
```python
# These values are tuned for OpenAI/Anthropic rate limits:
# - min=1s: Avoid hammering after transient errors
# - max=60s: Cap backoff to prevent long hangs
# - 6 attempts: ~2-3 minutes total with exponential backoff
```

Pros: Simpler, no new configuration
Cons: Users can't customize

### Recommendation

**Option B (Document)** - These values are well-tuned for production API usage. Making them configurable adds complexity without clear benefit.

### Implementation

Add explanatory comment above `@retry` decorators in both clients.

---

## P2-8: Inconsistent `strict=True` in zip()

### Problem

Some `zip()` calls use `strict=True`, others don't. This inconsistency can hide bugs where iterables have different lengths.

### Current State

```python
# WITH strict=True (catches length mismatches)
for pred, truth in zip(predictions, truths, strict=True):  # metrics.py
    ...

# WITHOUT strict=True (silently truncates)
for pred, truth in zip(predictions, truths):  # Some places
    ...
```

### Proposed Standard

Use `strict=True` by default unless explicitly handling different-length iterables.

### Audit Needed

```bash
# Find all zip() calls
grep -rn "zip(" src/giant/ --include="*.py" | grep -v strict
```

### Implementation

1. Run audit command
2. For each `zip()` without `strict`:
   - If iterables should be same length: add `strict=True`
   - If intentionally handling different lengths: add comment explaining why
3. Add linting rule (if possible with ruff)

### Files Likely Affected

```
src/giant/eval/runner.py          # Multiple zip() calls
src/giant/eval/answer_extraction.py
src/giant/llm/converters.py
src/giant/agent/context.py
```

---

## Implementation Priority

Recommended order based on impact and effort:

1. **P2-2** (Low effort, removes dead code or fixes test)
2. **P2-7** (Trivial, just add documentation)
3. **P2-8** (Low effort, improves safety)
4. **P2-1** (Low effort, establishes policy)
5. **P2-4** (Medium effort, cross-cutting change)

---

## Acceptance Criteria

For each item:
- [ ] Issue is resolved or documented
- [ ] All tests pass
- [ ] mypy and ruff checks pass
- [ ] Policy documented in CONTRIBUTING.md (if applicable)
