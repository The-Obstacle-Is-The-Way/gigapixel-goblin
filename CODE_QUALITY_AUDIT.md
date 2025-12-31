# Code Quality Audit Report

**Date:** 2025-12-31
**Auditor:** Claude Code
**Scope:** Full codebase review for anti-patterns, SOLID violations, DRY violations, potential bugs, and bad practices

---

## Executive Summary

The GIANT codebase is generally well-structured with good separation of concerns and comprehensive test coverage. However, this audit identified several areas for improvement across different priority levels.

**Total Issues Found:** 42
- **P0 (Critical):** 2
- **P1 (High):** 7
- **P2 (Medium):** 15
- **P3 (Low):** 12
- **P4 (Cosmetic):** 6

---

## P0 - Critical Issues

### P0-1: Broad Exception Catch in Image Pixel Counting

**File:** `src/giant/llm/converters.py:270`

```python
with Image.open(BytesIO(image_bytes)) as image:
    width, height = image.size
total_pixels += width * height
```

**Issue:** `count_image_pixels_in_messages` raises `ValueError` on invalid images, but this function is called during cost calculation in `anthropic_client.py:277`. If an image is corrupted or malformed, the entire API call fails with a confusing error during cost calculation, not during message processing.

**Impact:** Silent failures or confusing error messages during Anthropic API calls.

**Fix:** Wrap in try-except and log warning, defaulting to a reasonable pixel estimate or zero.

---

### P0-2: Race Condition in Circuit Breaker State Transitions

**File:** `src/giant/llm/circuit_breaker.py:86-95`

```python
@property
def state(self) -> CircuitState:
    if self._state == CircuitState.OPEN:
        if self._last_failure_time is not None:
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self.config.cooldown_seconds:
                self._transition_to_half_open()
    return self._state
```

**Issue:** The `state` property mutates internal state during a read operation. In async contexts with multiple concurrent LLM calls, this can cause race conditions where multiple calls simultaneously transition the circuit breaker, leading to inconsistent state.

**Impact:** Potential for concurrent calls to bypass circuit breaker or cause unexpected failures.

**Fix:** Use a lock for state transitions or separate the "check and transition" logic from the read property.

---

## P1 - High Priority Issues

### P1-1: DRY Violation - Duplicate System Prompt Extraction

**Files:** `src/giant/llm/converters.py:113-130` and `src/giant/llm/converters.py:209-226`

```python
def get_system_prompt_for_openai(messages: list[Message]) -> str | None:
    system_parts: list[str] = []
    for message in messages:
        if message.role == "system":
            for content in message.content:
                if content.type == "text" and content.text:
                    system_parts.append(content.text)
    return "\n".join(system_parts) if system_parts else None

def get_system_prompt_for_anthropic(messages: list[Message]) -> str | None:
    # IDENTICAL IMPLEMENTATION
```

**Issue:** These two functions are 100% identical. This violates DRY and means any bug fix or enhancement must be applied in two places.

**Fix:** Create a single `extract_system_prompt(messages)` function and alias or call from both.

---

### P1-2: Single Responsibility Violation - BenchmarkRunner

**File:** `src/giant/eval/runner.py`

**Issue:** `BenchmarkRunner` class handles too many responsibilities:
- Loading CSV benchmark items (lines 175-290)
- Resolving WSI paths (lines 292-320)
- Parsing options and labels (lines 322-456)
- Running agent on items (lines 458-915)
- Computing metrics (lines 968-1023)
- Saving results and trajectories (lines 1025-1061)

This violates the Single Responsibility Principle and makes the class hard to test and maintain (1062 lines).

**Fix:** Extract into smaller classes:
- `BenchmarkItemLoader` - CSV loading and parsing
- `MetricsCalculator` - metrics computation
- `ResultsPersistence` - saving results/trajectories
- `BenchmarkRunner` - orchestration only

---

### P1-3: Magic Sentinel Value Can Collide

**File:** `src/giant/eval/runner.py:46`

```python
_MISSING_LABEL_SENTINEL = -1
```

**Issue:** The sentinel value `-1` could theoretically collide with a valid label in some contexts. While documented as safe for PANDA (0-5) and 1-based option indices, this is fragile if benchmark formats change.

**Fix:** Use a more robust sentinel approach like `None` with explicit handling, or a dedicated `MissingLabel` class.

---

### P1-4: Potentially Infinite Loop in Invalid Region Handler

**File:** `src/giant/agent/runner.py:570-666`

```python
while True:
    self._consecutive_errors += 1
    if self._consecutive_errors >= self.config.max_retries:
        return self._build_error_result(...)
    # ... retry logic
```

**Issue:** If `max_retries` is set to 0 or negative, this becomes an infinite loop. While unlikely in practice, defensive programming should handle this.

**Fix:** Add validation in `AgentConfig` to ensure `max_retries >= 1`.

---

### P1-5: Inconsistent Error Handling for CONCH When Disabled

**File:** `src/giant/agent/runner.py:420-432`

```python
if not self.config.enable_conch:
    logger.warning(...)
    self._consecutive_errors += 1
    if self._consecutive_errors >= self.config.max_retries:
        return _StepDecision(
            run_result=self._build_error_result("Model requested CONCH but tool is disabled")
        )
    return _StepDecision()
```

**Issue:** When CONCH is disabled but the model requests it, we increment `_consecutive_errors` but return `_StepDecision()` without any feedback to the model. The model will keep requesting CONCH until max retries are exhausted, wasting API calls.

**Fix:** Provide error feedback message to the model explaining CONCH is disabled.

---

### P1-6: Unsafe Type Coercion in CLI

**File:** `src/giant/cli/main.py:553-564`

```python
def _trajectory_to_dict(trajectory: object | None) -> dict[str, object]:
    if trajectory is None:
        return {}
    if isinstance(trajectory, dict):
        return dict(trajectory)
    model_dump = getattr(trajectory, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        if isinstance(dumped, dict):
            return dumped
    return {}
```

**Issue:** The function accepts `object | None` which is overly permissive. If something unexpected is passed, it silently returns an empty dict, hiding bugs.

**Fix:** Use proper typing `Trajectory | dict[str, Any] | None` and raise `TypeError` for unexpected types.

---

### P1-7: Missing Budget Validation Allows Negative Values

**File:** `src/giant/eval/runner.py:74`

```python
budget_usd: float | None = Field(default=None, ge=0.0)
```

**Issue:** While Pydantic validates `ge=0.0`, the CLI accepts `--budget-usd` and the `AgentConfig` doesn't validate. This could lead to unexpected behavior if negative budget is passed through other paths.

**File:** `src/giant/agent/runner.py:148`

```python
budget_usd: float | None = None  # No validation
```

**Fix:** Add validation in `AgentConfig` dataclass with `__post_init__`.

---

## P2 - Medium Priority Issues

### P2-1: Inconsistent Frozen Dataclass Usage

**Files:** Various

Some dataclasses use `frozen=True`:
- `CroppedImage` (crop_engine.py:52)
- `OverlayStyle` (overlay.py:26)
- `_StepDecision` (runner.py:118)
- `ExtractedAnswer` (answer_extraction.py:32)

Others don't:
- `AgentConfig` (runner.py:130)
- `GIANTAgent` (runner.py:162)
- `CircuitBreaker` (circuit_breaker.py:58)
- `CircuitBreakerConfig` (circuit_breaker.py:41)

**Issue:** Inconsistent immutability semantics make it harder to reason about object lifecycle and thread safety.

**Fix:** Document the policy for when to use `frozen=True` and apply consistently.

---

### P2-2: Type `Any` Used Too Liberally

**Files:** Multiple

```python
# circuit_breaker.py:134
_circuit_breaker: CircuitBreaker[Any] = field(init=False, repr=False)

# runner.py (eval)
metrics: dict[str, Any] = Field(default_factory=dict)
```

**Issue:** Using `Any` defeats the purpose of type checking and can hide bugs.

**Fix:** Use more specific types or define proper TypedDict/dataclass for metrics.

---

### P2-3: Test Fixture Using Old API Response Structure

**File:** `tests/conftest.py:40-71`

```python
@pytest.fixture
def mock_api_responses() -> dict[str, Any]:
    return {
        "openai_completion": {
            "choices": [{"message": {"role": "assistant", ...}}],
            ...
        },
```

**Issue:** The mock structure uses the old Chat Completions API format, but the code uses the Responses API. This fixture is misleading and could lead to incorrect test assumptions.

**Fix:** Update to match Responses API structure or remove if unused.

---

### P2-4: Hardcoded JPEG Quality Throughout

**Files:** Multiple

```python
# crop_engine.py:137
jpeg_quality: int = 85

# runner.py:851
def _encode_image_base64(self, image: Image.Image, quality: int = 85) -> str:

# config.py:81
JPEG_QUALITY: int = 85
```

**Issue:** JPEG quality is defined in config but hardcoded in multiple places instead of using the config value.

**Fix:** Use `settings.JPEG_QUALITY` consistently.

---

### P2-5: Inconsistent Logging Patterns

**Files:** Multiple

Some files use:
```python
logger.info("Message", wsi=str(wsi_path))  # Structured
```

Others use:
```python
logger.info("Message: %s", value)  # Format string
```

**Issue:** Inconsistent logging makes log aggregation and parsing harder.

**Fix:** Standardize on structured logging (key-value) throughout.

---

### P2-6: Protocol with Empty TYPE_CHECKING Block

**File:** `src/giant/llm/protocol.py:20-21`

```python
if TYPE_CHECKING:
    pass
```

**Issue:** Empty TYPE_CHECKING block serves no purpose.

**Fix:** Remove or add the intended imports.

---

### P2-7: Nested Import Anti-Pattern

**File:** `src/giant/agent/runner.py:508`

```python
from PIL import Image  # noqa: PLC0415
```

**Issue:** Import inside a method is an anti-pattern. While the noqa comment shows awareness, this is still suboptimal.

**Fix:** Move to top of file if used in multiple methods, or document why deferred import is necessary (e.g., optional dependency).

---

### P2-8: Missing Validation for num_guides = 0

**File:** `src/giant/geometry/overlay.py:44`

```python
num_guides: int = 4
```

**Issue:** `num_guides` could be set to 0, which would cause `step_x = thumb_w / 1` and no guides drawn. While not a crash, it's unexpected behavior.

**Fix:** Add `Field(ge=1)` validation or document that 0 means no guides.

---

### P2-9: Potential Division by Zero in Metrics

**File:** `src/giant/eval/metrics.py:75-76`

```python
recalls = []
for cls, count in class_counts.items():
    recall = class_correct[cls] / count
    recalls.append(recall)
return sum(recalls) / len(recalls)
```

**Issue:** If `recalls` is empty (no classes in truths), this raises `ZeroDivisionError`. While the function validates non-empty inputs, edge cases with all-same predictions could theoretically cause issues.

**Fix:** Add defensive check for empty recalls list.

---

### P2-10: Mutable Default Pattern with field()

**File:** `src/giant/agent/context.py:55-56`

```python
trajectory: Trajectory = field(init=False)
_prompt_builder: PromptBuilder = field(init=False, repr=False)
```

**Issue:** These are assigned in `__post_init__` which is correct, but the pattern of `field(init=False)` without `default_factory` can be confusing. The fields appear uninitialized until `__post_init__` runs.

**Fix:** Consider using `field(default_factory=...)` or documenting the pattern.

---

### P2-11: Callback Hell in _handle_step_action

**File:** `src/giant/agent/runner.py:349-371`

```python
async def _handle_step_action(
    self, step_response: StepResponse, messages: list[Message]
) -> _StepDecision:
    action = step_response.action
    if isinstance(action, FinalAnswerAction):
        ...
        return _StepDecision(run_result=self._handle_answer(step_response))
    if isinstance(action, BoundingBoxAction):
        return await self._handle_crop_action(step_response, action, messages)
    if isinstance(action, ConchAction):
        return await self._handle_conch_action(step_response, action)
    if self._context.is_final_step:
        return _StepDecision(break_to_force_answer=True)
    return _StepDecision()
```

**Issue:** Multiple return paths with different `_StepDecision` construction patterns. The logic for what happens when action type is unknown (falls through to final check) is implicit.

**Fix:** Use match statement (Python 3.10+) or add explicit else clause with logging.

---

### P2-12: Path Traversal Check Not Comprehensive

**File:** `src/giant/eval/runner.py:543-554`

```python
@staticmethod
def _validate_run_id(run_id: str) -> None:
    run_id_path = Path(run_id)
    if (
        run_id_path.is_absolute()
        or ".." in run_id_path.parts
        or run_id_path.name != run_id
    ):
        raise ValueError(...)
```

**Issue:** Checks `run_id` but similar validation isn't consistently applied to `item_id` when saving trajectories (line 1044 uses `_safe_filename_component` but this is a different approach).

**Fix:** Consolidate path safety validation into a single utility function.

---

### P2-13: Retry Logic Uses Hardcoded Exponential Backoff

**Files:** `openai_client.py:207-212`, `anthropic_client.py:195-200`

```python
@retry(
    wait=wait_random_exponential(min=1, max=60),
    stop=stop_after_attempt(6),
    ...
)
```

**Issue:** Retry parameters are hardcoded in decorators instead of being configurable through settings.

**Fix:** Make retry parameters configurable or document why fixed values are intentional.

---

### P2-14: Inconsistent Use of strict=True in zip()

**Files:** Multiple

Some places use `strict=True`:
```python
for pred, truth in zip(predictions, truths, strict=True):  # metrics.py:36
```

Others don't:
```python
for i, ds in enumerate(metadata.level_downsamples):  # level_selector.py:172
```

**Issue:** Inconsistent zip strictness can hide length mismatches.

**Fix:** Use `strict=True` consistently where appropriate.

---

### P2-15: Message Content Mutation in Context Manager

**File:** `src/giant/agent/context.py:280-282`

```python
text_content = next((c for c in msg.content if c.type == "text"), None)
if text_content is not None and text_content.text is not None:
    text_content.text = f"{conch_summary}\n\n{text_content.text}"
```

**Issue:** This mutates the `MessageContent` object inside the message. If `Message` or `MessageContent` were intended to be immutable (they're Pydantic models), this is unexpected mutation.

**Fix:** Create a new `MessageContent` instead of mutating, or document that mutation is intentional.

---

## P3 - Low Priority Issues

### P3-1: Assert Used for Runtime Validation

**Files:** Multiple

```python
# runner.py:678
assert isinstance(action, FinalAnswerAction)

# context.py:256
assert isinstance(action, ConchAction)
```

**Issue:** `assert` statements can be disabled with `python -O`. For runtime validation, use explicit if/raise.

**Fix:** Replace with explicit type checks that raise appropriate exceptions.

---

### P3-2: Unused Imports in TYPE_CHECKING Blocks

**File:** `src/giant/agent/runner.py:54-55`

```python
if TYPE_CHECKING:
    from PIL import Image
```

But PIL.Image is also imported at runtime in line 508. This TYPE_CHECKING import is unused.

**Fix:** Remove the TYPE_CHECKING import.

---

### P3-3: Inconsistent String Quote Style

**Files:** Throughout

Most places use double quotes, but some use single quotes. While Black handles this, manual strings are inconsistent.

**Fix:** Run Black with consistent quote settings.

---

### P3-4: Missing __all__ in Some Modules

**Files:** Several `__init__.py` files

`src/giant/llm/__init__.py` has proper `__all__`, but others like `src/giant/geometry/__init__.py` may not.

**Fix:** Add `__all__` to all public package `__init__.py` files.

---

### P3-5: Docstring Missing for __post_init__

**File:** `src/giant/agent/context.py:58-64`

```python
def __post_init__(self) -> None:
    """Initialize trajectory and prompt builder."""
```

**Issue:** Docstring is minimal. Should document what gets initialized and any side effects.

**Fix:** Expand docstring to describe initialization behavior.

---

### P3-6: Magic Number in Font Fallback

**File:** `src/giant/geometry/overlay.py:175-203`

```python
return ImageFont.truetype("DejaVuSans.ttf", self.style.font_size)
```

**Issue:** Font names are hardcoded strings.

**Fix:** Define as constants or make configurable.

---

### P3-7: Long Method in BenchmarkRunner

**File:** `src/giant/eval/runner.py:458-541` (run_benchmark)

**Issue:** Method is 83 lines long, doing multiple things. While refactored into helpers, the main method is still complex.

**Fix:** Further decomposition or clearer step comments.

---

### P3-8: Test Uses Mock Without spec

**File:** `tests/unit/agent/test_runner.py:38-54`

```python
@pytest.fixture
def mock_wsi_reader() -> MagicMock:
    reader = MagicMock()
    reader.__enter__ = MagicMock(return_value=reader)
```

**Issue:** `MagicMock()` without `spec=WSIReader` can accept any attribute access, hiding API mismatches.

**Fix:** Use `MagicMock(spec=WSIReader)` to catch interface mismatches.

---

### P3-9: Redundant Type Annotation

**File:** `src/giant/llm/circuit_breaker.py:59`

```python
@dataclass
class CircuitBreaker(Generic[T]):
```

**Issue:** The generic type `T` is defined but never used in the class body. It appears to be left over from a previous design.

**Fix:** Remove `Generic[T]` if not used, or document its purpose.

---

### P3-10: Confusing Variable Naming

**File:** `src/giant/eval/runner.py:581`

```python
budget_state = {"total_cost": sum(r.cost_usd for r in checkpoint.results)}
```

**Issue:** Using a dict as mutable state container for closures is a known pattern but can be confusing. Named `budget_state` but only contains `total_cost`.

**Fix:** Use a simple mutable container class or document the pattern.

---

### P3-11: Exception Chaining Missing in Some Places

**File:** `src/giant/config.py:188-192`

```python
except OSError as e:
    raise ValueError(...) from e
```

Good! But other places don't chain:

**File:** `src/giant/cli/main.py:190`

```python
raise typer.Exit(1) from None
```

**Issue:** Using `from None` explicitly suppresses the original exception context.

**Fix:** Only use `from None` when intentionally suppressing; otherwise use `from e`.

---

### P3-12: Inconsistent Return Type Annotations

**File:** `src/giant/agent/runner.py:282-288`

```python
def _infer_provider_name(self) -> str | None:
    name = type(self.llm_provider).__name__.lower()
    if "openai" in name:
        return "openai"
    if "anthropic" in name:
        return "anthropic"
    return None
```

**Issue:** This heuristic-based provider detection is fragile. If someone creates `MyOpenAIWrapper`, it would match "openai".

**Fix:** Add a `get_provider_name()` method to the `LLMProvider` protocol.

---

## P4 - Cosmetic Issues

### P4-1: Inconsistent Class Organization

Some classes put properties before methods, others don't. Methods aren't consistently ordered (public before private).

**Fix:** Establish and document class organization conventions.

---

### P4-2: Long Lines in Some Files

Some lines exceed 88-100 characters despite Black formatting, usually in string literals or complex expressions.

**Fix:** Break long strings/expressions for readability.

---

### P4-3: Missing Blank Lines in Some Test Classes

Test methods sometimes lack blank lines between them.

**Fix:** Ensure consistent spacing.

---

### P4-4: Inconsistent Comment Style

Some comments use `#`, others use `# ` (with space). Some inline comments are lengthy.

**Fix:** Run linter with consistent comment style rules.

---

### P4-5: Missing Type Hints in Test Fixtures

Some test fixtures don't have return type annotations.

**Fix:** Add return types to all fixtures.

---

### P4-6: Verbose Imports

**File:** `src/giant/llm/__init__.py`

Long import lists could use import grouping for readability.

**Fix:** Group related imports with blank lines.

---

## Recommendations

### Immediate Actions (P0)
1. Fix the race condition in circuit breaker state transitions
2. Add defensive error handling in `count_image_pixels_in_messages`

### Short-term Actions (P1-P2)
1. Refactor `BenchmarkRunner` into smaller classes
2. Consolidate duplicate functions (system prompt extraction)
3. Add missing validations (budget, max_retries)
4. Standardize logging patterns

### Long-term Actions (P3-P4)
1. Add `spec` to all MagicMock usages in tests
2. Standardize code organization patterns
3. Remove unused generic type parameters
4. Add `__all__` to all packages

---

## Testing Recommendations

1. **Add integration tests for circuit breaker under concurrent load**
2. **Add property-based tests for coordinate validation**
3. **Add mutation testing to verify test quality**
4. **Add coverage for error paths in cost calculation**

---

## Architectural Notes

The overall architecture is sound:
- Good separation between agent, LLM, WSI, and evaluation concerns
- Protocol-based abstraction for providers enables testing
- Pydantic models provide good validation

Key strengths:
- Comprehensive error handling in LLM providers
- Good use of dataclasses and Pydantic
- Well-documented code with clear docstrings
- Type hints throughout

Areas for improvement:
- Some classes are too large (BenchmarkRunner)
- Inconsistent patterns across similar code
- Could benefit from more dependency injection
