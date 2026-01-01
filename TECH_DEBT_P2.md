# Technical Debt Spec: P2 Medium Priority Items

**Priority:** P2 (Medium)
**Total Items:** 4 remaining
**Effort:** Small to Medium each
**Status:** ACTIONABLE - Ready for implementation
**Last Verified:** 2025-12-31

---

## Overview

These are medium-priority code quality issues that should be addressed before the next major release. Each requires either a design decision or codebase-wide changes.

| ID | Issue | Effort | Status | Action |
|----|-------|--------|--------|--------|
| P2-1 | Inconsistent frozen dataclass usage | Small | READY | Document policy, update 3 files |
| P2-2 | Unused test fixture (dead code) | Trivial | READY | Delete 32 lines |
| P2-4 | Inconsistent logging patterns | Medium | READY | Update 9 files |
| P2-7 | Hardcoded retry parameters | Trivial | READY | Add documentation comments |

---

## P2-1: Inconsistent Frozen Dataclass Usage

### Problem

Some dataclasses use `frozen=True`, others don't. No documented policy.

### Current State (Verified 2025-12-31)

**FROZEN dataclasses (14 total) - CORRECT:**
```
src/giant/data/tcga.py:29           @dataclass(frozen=True) class GdcFile
src/giant/eval/answer_extraction.py:32  @dataclass(frozen=True) class ExtractedAnswer
src/giant/eval/wsi_resolver.py:17   @dataclass(frozen=True) class WSIPathResolver
src/giant/eval/runner.py:115        @dataclass(frozen=True) class _ItemRunState
src/giant/eval/metrics.py:79        @dataclass(frozen=True) class BootstrapResult
src/giant/core/crop_engine.py:53    @dataclass(frozen=True) class CroppedImage
src/giant/core/baselines.py:30      @dataclass(frozen=True) class BaselineRequest
src/giant/cli/runners.py:51         @dataclass(frozen=True) class DataCheckResult
src/giant/agent/runner.py:118       @dataclass(frozen=True) class _StepDecision
src/giant/geometry/overlay.py:26    @dataclass(frozen=True) class OverlayStyle
src/giant/wsi/types.py:14           @dataclass(frozen=True) class WSIMetadata
```

**FROZEN pydantic models (3 total) - CORRECT:**
```
src/giant/geometry/primitives.py:15  class Point(BaseModel, frozen=True)
src/giant/geometry/primitives.py:39  class Size(BaseModel, frozen=True)
src/giant/geometry/primitives.py:67  class Region(BaseModel, frozen=True)
```

**NON-FROZEN dataclasses (9 total) - REVIEW NEEDED:**
```
src/giant/cli/runners.py:25         @dataclass class InferenceResult      # Has mutable state
src/giant/cli/runners.py:39         @dataclass class BenchmarkResult      # Has mutable state
src/giant/llm/anthropic_client.py:113  @dataclass class AnthropicProvider  # Has _client
src/giant/llm/openai_client.py:128  @dataclass class OpenAIProvider       # Has _client
src/giant/llm/circuit_breaker.py:41 @dataclass class CircuitBreakerConfig # Config object
src/giant/llm/circuit_breaker.py:58 @dataclass class CircuitBreaker       # Has mutable state
src/giant/agent/context.py:29       @dataclass class ContextManager       # Has mutable state
src/giant/agent/runner.py:130       @dataclass class AgentConfig          # Config object
src/giant/agent/runner.py:162       @dataclass class GIANTAgent           # Has mutable state
```

**NON-FROZEN pydantic models (16 total) - CORRECT AS-IS:**
```
src/giant/data/schemas.py:44        class BenchmarkItem(BaseModel)        # Mutable
src/giant/data/schemas.py:73        class BenchmarkResult(BaseModel)      # Mutable
src/giant/eval/resumable.py:63      class CheckpointState(BaseModel)      # Mutable
src/giant/eval/runner.py:50         class EvaluationConfig(BaseModel)     # Config
src/giant/eval/runner.py:89         class EvaluationResults(BaseModel)    # Mutable
src/giant/llm/protocol.py:29        class BoundingBoxAction(BaseModel)    # Value object
src/giant/llm/protocol.py:43        class FinalAnswerAction(BaseModel)    # Value object
src/giant/llm/protocol.py:57        class ConchAction(BaseModel)          # Value object
src/giant/llm/protocol.py:84        class StepResponse(BaseModel)         # Value object
src/giant/llm/protocol.py:100       class TokenUsage(BaseModel)           # Value object
src/giant/llm/protocol.py:113       class LLMResponse(BaseModel)          # Value object
src/giant/llm/protocol.py:131       class MessageContent(BaseModel)       # Value object
src/giant/llm/protocol.py:147       class Message(BaseModel)              # Value object
src/giant/agent/runner.py:98        class RunResult(BaseModel)            # Value object
src/giant/agent/trajectory.py:20    class Turn(BaseModel)                 # Value object
src/giant/agent/trajectory.py:50    class Trajectory(BaseModel)           # Value object
```

### Recommended Policy

| Category | Frozen | Rationale |
|----------|--------|-----------|
| Value objects (coordinates, results, actions) | Yes | Immutable by nature |
| Configuration objects (small, read-only) | Yes | Prevents accidental mutation |
| Service classes (providers, agents) | No | Have mutable internal state |
| Data transfer objects (schemas) | No | Often mutated during processing |

### Implementation

**Step 1: Make config dataclasses frozen (2 files)**

File: `src/giant/llm/circuit_breaker.py:41`
```python
# BEFORE
@dataclass
class CircuitBreakerConfig:

# AFTER
@dataclass(frozen=True)
class CircuitBreakerConfig:
```

File: `src/giant/agent/runner.py:130`
```python
# BEFORE
@dataclass
class AgentConfig:

# AFTER
@dataclass(frozen=True)
class AgentConfig:
```

**Step 2: Make protocol value objects frozen (1 file)**

File: `src/giant/llm/protocol.py`

Add `frozen=True` to these Pydantic models (lines 29, 43, 57, 84, 100, 113, 131, 147):
```python
class BoundingBoxAction(BaseModel, frozen=True):  # line 29
class FinalAnswerAction(BaseModel, frozen=True):  # line 43
class ConchAction(BaseModel, frozen=True):        # line 57
class StepResponse(BaseModel, frozen=True):       # line 84
class TokenUsage(BaseModel, frozen=True):         # line 100
class LLMResponse(BaseModel, frozen=True):        # line 113
class MessageContent(BaseModel, frozen=True):     # line 131
class Message(BaseModel, frozen=True):            # line 147
```

**Step 3: Document policy**

Add to `docs/development/CONTRIBUTING.md`:
```markdown
## Immutability Policy

- **Value objects** (coordinates, parsed responses): Use `frozen=True`
- **Config objects** (small, read-only after init): Use `frozen=True`
- **Service classes** (with mutable state): Do NOT use `frozen=True`
- **DTOs** (schemas, results): Case-by-case based on usage
```

### Verification Commands

```bash
# Find frozen dataclasses
grep -rn "@dataclass(frozen=True)" src/

# Find non-frozen dataclasses
grep -rn "@dataclass$" src/

# Find frozen pydantic models
grep -rn "BaseModel, frozen=True" src/

# Run tests after changes
uv run pytest tests/unit -x
```

---

## P2-2: Unused Test Fixture (Dead Code)

### Problem

`tests/conftest.py:40-71` defines `mock_api_responses` fixture that is **never used**.

### Verification (2025-12-31)

```bash
$ grep -rn "mock_api_responses" tests/
tests/conftest.py:40:def mock_api_responses() -> dict[str, Any]:
```

Only the definition is found. No test imports or uses this fixture.

### Implementation

**Delete lines 39-71 from `tests/conftest.py`:**

```python
# DELETE THIS ENTIRE BLOCK (lines 39-71):
@pytest.fixture
def mock_api_responses() -> dict[str, Any]:
    """Provide mock API response structures for LLM tests."""
    return {
        "openai_completion": {
            "id": "test-completion-id",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Test response",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
            },
        },
        "anthropic_message": {
            "id": "test-message-id",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "Test response"}],
            "stop_reason": "end_turn",
            "usage": {
                "input_tokens": 100,
                "output_tokens": 50,
            },
        },
    }
```

### Verification

```bash
# Ensure tests still pass
uv run pytest tests/unit -x

# Verify fixture is gone
grep -rn "mock_api_responses" tests/
# Should return nothing
```

---

## P2-4: Inconsistent Logging Patterns

### Problem

Mixed logging approaches across the codebase:
- Some files use `import logging` + `logging.getLogger(__name__)`
- Some files use `from giant.utils.logging import get_logger`

### Current State (Verified 2025-12-31)

**Files using standard logging (NEED UPDATE - 9 files):**
```
src/giant/data/download.py:13       import logging
src/giant/eval/resumable.py:12      import logging
src/giant/geometry/overlay.py:14    import logging
src/giant/agent/runner.py:20        import logging
src/giant/eval/runner.py:17         import logging
src/giant/llm/circuit_breaker.py:20 import logging
src/giant/llm/anthropic_client.py:17 import logging
src/giant/llm/openai_client.py:17   import logging
src/giant/utils/logging.py:7        import logging  # OK - this IS the logging module
```

**Files using structured logging (CORRECT - 6 files):**
```
src/giant/data/tcga.py:22           from giant.utils.logging import get_logger
src/giant/data/download.py:19       from giant.utils.logging import get_logger  # MIXED!
src/giant/cli/visualizer.py:12      from giant.utils.logging import get_logger
src/giant/cli/main.py:18            from giant.utils.logging import get_logger
src/giant/cli/runners.py:19         from giant.utils.logging import get_logger
```

### Implementation

**For each of the 8 files (excluding utils/logging.py and download.py which already has it):**

**Pattern to apply:**

```python
# BEFORE
import logging
# ...
logger = logging.getLogger(__name__)

# AFTER
from giant.utils.logging import get_logger
# ...
logger = get_logger(__name__)
```

**File-by-file changes:**

1. `src/giant/eval/resumable.py:12`
   - Replace `import logging` with `from giant.utils.logging import get_logger`
   - Replace `logger = logging.getLogger(__name__)` with `logger = get_logger(__name__)`

2. `src/giant/geometry/overlay.py:14`
   - Same pattern

3. `src/giant/agent/runner.py:20`
   - Same pattern

4. `src/giant/eval/runner.py:17`
   - Same pattern

5. `src/giant/llm/circuit_breaker.py:20`
   - Same pattern

6. `src/giant/llm/anthropic_client.py:17`
   - Same pattern

7. `src/giant/llm/openai_client.py:17`
   - Same pattern

8. `src/giant/data/download.py`
   - Remove `import logging` on line 13 (already has structured import on line 19)

### Verification

```bash
# Check no files use import logging (except utils/logging.py itself)
grep -rn "^import logging$" src/giant/ | grep -v "utils/logging.py"
# Should return nothing

# Run tests
uv run pytest tests/unit -x

# Check type hints
uv run mypy src/giant
```

---

## P2-7: Hardcoded Retry Parameters

### Problem

Retry logic uses hardcoded values instead of configurable settings:

```python
# openai_client.py:207-212 and anthropic_client.py:192-197
@retry(
    wait=wait_random_exponential(min=1, max=60),
    stop=stop_after_attempt(6),
    retry=retry_if_exception_type((RateLimitError, APIConnectionError)),
)
```

### Decision: Document, Don't Configure

**Rationale:** These values are tuned for production API rate limits:
- `min=1s`: Avoid hammering after transient errors
- `max=60s`: Cap backoff to prevent long hangs
- `6 attempts`: ~2-3 minutes total with exponential backoff

Making them configurable adds complexity without clear benefit.

### Implementation

**Add documentation comment above `@retry` in both files:**

File: `src/giant/llm/openai_client.py:206-212`
```python
    # Retry configuration tuned for OpenAI API rate limits:
    # - min=1s wait prevents hammering on transient errors
    # - max=60s caps backoff to avoid long hangs
    # - 6 attempts provides ~2-3 min total with exponential backoff
    # These values match production recommendations; do not configure.
    @retry(
        wait=wait_random_exponential(min=1, max=60),
        stop=stop_after_attempt(6),
        retry=retry_if_exception_type((RateLimitError, APIConnectionError)),
    )
```

File: `src/giant/llm/anthropic_client.py:191-197`
```python
    # Retry configuration tuned for Anthropic API rate limits:
    # - min=1s wait prevents hammering on transient errors
    # - max=60s caps backoff to avoid long hangs
    # - 6 attempts provides ~2-3 min total with exponential backoff
    # These values match production recommendations; do not configure.
    @retry(
        wait=wait_random_exponential(min=1, max=60),
        stop=stop_after_attempt(6),
        retry=retry_if_exception_type((RateLimitError, APIConnectionError)),
    )
```

### Verification

```bash
# Check comments are in place
grep -A5 "Retry configuration" src/giant/llm/*.py

# Run tests
uv run pytest tests/unit -x
```

---

## Implementation Priority

Recommended order based on effort and value:

1. **P2-2** (5 min) - Delete unused fixture, trivial cleanup
2. **P2-7** (5 min) - Add documentation comments only
3. **P2-1** (30 min) - Add `frozen=True` to config classes + protocol
4. **P2-4** (1-2 hours) - Update 8 files to use structured logging

---

## Acceptance Criteria

For each item:
- [ ] Issue is resolved as specified
- [ ] All 858+ unit tests pass: `uv run pytest tests/unit`
- [ ] Type checking passes: `uv run mypy src/giant`
- [ ] Linting passes: `uv run ruff check .`
- [ ] Changes committed with descriptive message

---

## Commit Messages

```
fix(tests): remove unused mock_api_responses fixture

chore(llm): document retry parameter rationale

refactor(core): add frozen=True to config dataclasses

refactor(logging): standardize on structured logging
```
