# Technical Debt Spec: P3 Low Priority Items

**Priority:** P3 (Low)
**Total Items:** 13
**Effort:** Trivial to Small each
**Status:** DEFERRED - Low value, fix opportunistically
**Last Verified:** 2025-12-31

---

## Overview

These are low-priority code quality issues. Fix them opportunistically when working in the affected files, or ignore entirely.

| ID | Issue | File | Effort | Recommendation |
|----|-------|------|--------|----------------|
| P3-1 | Circuit breaker state mutates on read | `circuit_breaker.py:84` | Small | Skip |
| P3-2 | No CONCH disabled feedback | `context.py` | Small | Skip |
| P3-3 | Magic sentinel -1 | `runner.py:43-45` | Medium | Skip (safe by design) |
| P3-5 | Unused TYPE_CHECKING import | `agent/runner.py:54-55` | Trivial | Fix if nearby |
| P3-6 | Nested import anti-pattern | `agent/runner.py:508` | Trivial | Skip (intentional) |
| P3-7 | No negative budget validation | `agent/runner.py:135` | Trivial | Fix if nearby |
| P3-9 | Unused Generic[T] parameter | `circuit_breaker.py:59` | Trivial | Fix if nearby |
| P3-10 | Confusing budget_state name | `eval/runner.py:581` | Trivial | Skip |
| P3-11 | Inconsistent exception chaining | Various | Small | Skip |
| P3-12 | Heuristic provider detection | `agent/runner.py:282-288` | Small | Fix if adding providers |
| P3-13 | Message content mutation | `context.py:281-282` | Small | Skip |
| P3-14 | Path validation not consolidated | Various | Small | Skip |
| P3-15 | Long run_benchmark method | `eval/runner.py` | Small | Deferred to P1-2 |

---

## P3-5: Unused TYPE_CHECKING Import (Trivial)

**File:** `src/giant/agent/runner.py:54-55`

```python
# CURRENT (lines 54-55)
if TYPE_CHECKING:
    from PIL import Image as PILImage

# Line 508 imports PIL at runtime:
from PIL import Image  # noqa: PLC0415
```

**Fix:** Remove lines 54-55 (the TYPE_CHECKING block is dead code since PIL is imported at runtime anyway).

---

## P3-7: No Negative Budget Validation (Trivial)

**File:** `src/giant/agent/runner.py:135`

```python
# CURRENT
budget_usd: float | None = None

# FIX - add validation
budget_usd: float | None = Field(default=None, ge=0.0)
```

**Note:** Requires changing `AgentConfig` from `@dataclass` to `BaseModel`, or adding `__post_init__` validation.

---

## P3-9: Unused Generic[T] Parameter (Trivial)

**File:** `src/giant/llm/circuit_breaker.py:59`

```python
# CURRENT
class CircuitBreaker(Generic[T]):
    # T is never used anywhere in the class

# FIX
class CircuitBreaker:
    # Remove Generic[T]
```

---

## P3-12: Heuristic Provider Detection (Small)

**File:** `src/giant/agent/runner.py:282-288`

```python
# CURRENT (fragile string matching)
name = type(self.llm_provider).__name__.lower()
if "openai" in name:
    # ...
elif "anthropic" in name:
    # ...
```

**Better approach:** Add `get_provider_type()` method to `LLMProvider` protocol:

```python
# In protocol.py
class LLMProvider(Protocol):
    def get_provider_type(self) -> Literal["openai", "anthropic", "gemini"]: ...

# In agent/runner.py
provider_type = self.llm_provider.get_provider_type()
if provider_type == "openai":
    # ...
```

---

## Items to Skip (Rationale)

### P3-1: Circuit Breaker State Mutates
The `state` property can trigger state transitions during reads. In async contexts, this is theoretically racey but Python's cooperative async means transitions happen atomically. Impact is minimal (off-by-one counts at worst). Not worth refactoring.

### P3-3: Magic Sentinel -1
`_MISSING_LABEL_SENTINEL = -1` is safe because:
- PANDA labels are 0-5
- Options are 1-indexed
- -1 never matches valid labels

### P3-6: Nested Import
The `from PIL import Image` inside methods is intentional lazy loading to avoid importing PIL when not needed. The `# noqa: PLC0415` comments confirm this is deliberate.

### P3-10, P3-11, P3-13, P3-14, P3-15
These are all minor style/consistency issues. Low value compared to effort.

---

## When to Address

Only fix these if:
1. You're already modifying the affected file for another reason
2. A new bug is discovered related to the issue
3. Test coverage drops below 90%

**Do not create dedicated PRs for P3 items.**
