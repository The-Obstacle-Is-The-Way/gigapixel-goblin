# Technical Debt Spec: P1-2 BenchmarkRunner Refactor

**Priority:** P1 (High)
**Effort:** Large (2-4 days)
**Risk:** LOW for correctness, MEDIUM for maintainability
**Status:** DEFERRED - Awaiting capacity
**Last Verified:** 2025-12-31 (all line numbers confirmed)

---

## Problem Statement

`src/giant/eval/runner.py` is 1064 lines with the `BenchmarkRunner` class handling 6+ distinct responsibilities:

1. **CSV Loading & Parsing** - Reading MultiPathQA CSV, parsing options, validating schema
2. **WSI Path Resolution** - Mapping benchmark IDs to WSI file paths
3. **Agent Execution** - Running GIANT/thumbnail/patch modes on items
4. **Answer Extraction & Scoring** - Extracting labels, computing correctness
5. **Metrics Computation** - Accuracy, balanced accuracy, bootstrap confidence intervals
6. **Persistence** - Saving results, trajectories, checkpoints

This violates the Single Responsibility Principle (SRP), making the class:
- Hard to test individual components in isolation
- Difficult for new developers to understand
- Risky to modify (changes may have unintended side effects)

---

## Current Architecture

```
BenchmarkRunner (1064 lines)
├── __init__()
├── load_benchmark_items()          # Responsibility 1: CSV Loading
│   ├── _validate_csv_schema()
│   ├── _parse_options()
│   ├── _inject_options()
│   ├── _validate_truth_label_int()
│   └── _parse_truth_label()
├── _resolve_wsi_path()             # Responsibility 2: Path Resolution
├── run_benchmark()                 # Responsibility 3: Orchestration
│   ├── _validate_run_id()
│   ├── _safe_filename_component()
│   ├── _run_pending_items()
│   └── _run_worker()
├── _run_single_item()              # Responsibility 4: Execution
│   ├── _run_item_giant()
│   ├── _run_item_thumbnail()
│   ├── _run_item_patch()
│   ├── _build_item_result()
│   ├── _majority_vote()
│   └── _select_majority_prediction()
├── _compute_metrics()              # Responsibility 5: Metrics
└── _save_results()                 # Responsibility 6: Persistence
    └── _save_trajectory()
```

---

## Proposed Architecture

Extract into 4 focused classes:

```
src/giant/eval/
├── runner.py           # EvaluationOrchestrator (orchestration only, ~200 lines)
├── loader.py           # BenchmarkItemLoader (CSV parsing, ~150 lines)
├── metrics.py          # Existing metric functions (keep)
├── persistence.py      # ResultsPersistence (saving, ~100 lines)
└── executor.py         # ItemExecutor (agent runs, ~300 lines)
```

### 1. BenchmarkItemLoader (`loader.py`)

**Responsibility:** Load and validate benchmark items from CSV.

```python
@dataclass
class BenchmarkItemLoader:
    """Loads benchmark items from MultiPathQA CSV format."""

    csv_path: Path
    wsi_root: Path
    benchmark_name: str
    skip_missing_wsis: bool = False

    def load(self) -> list[BenchmarkItem]:
        """Load all items, resolving WSI paths."""
        ...

    @staticmethod
    def validate_csv_schema(reader: csv.DictReader, csv_path: Path) -> None:
        """Validate required columns exist."""
        ...

    @staticmethod
    def parse_options(options_str: str) -> list[str]:
        """Parse options field (JSON, Python literal, or pipe-delimited)."""
        ...

    @staticmethod
    def parse_truth_label(
        benchmark_name: str,
        answer: str,
        options: list[str] | None
    ) -> int:
        """Convert truth answer to integer label."""
        ...
```

**Files to extract from:**
- `load_benchmark_items()` (lines 175-290)
- `_validate_csv_schema()` (lines 165-173)
- `_resolve_wsi_path()` (lines 292-320)
- `_parse_options()` (lines 323-360)
- `_inject_options()` (lines 362-375)
- `_validate_truth_label_int()` (lines 377-402)
- `_parse_truth_label()` (lines 404-455)

**Tests to migrate:**
- `tests/unit/eval/test_runner.py::TestLoadBenchmarkItems` (includes options parsing)
- `tests/unit/eval/test_runner.py::TestResolveWsiPath`
- `tests/unit/eval/test_runner.py::TestWsiNotFound`
- `tests/unit/eval/test_runner.py::TestTruthLabelParsing`

---

### 2. ItemExecutor (`executor.py`)

**Responsibility:** Execute agent on single items (GIANT/thumbnail/patch modes).

```python
@dataclass
class ItemExecutor:
    """Executes evaluation modes on benchmark items."""

    llm_provider: LLMProvider
    config: EvaluationConfig
    results_dir: Path

    async def execute(self, item: BenchmarkItem) -> BenchmarkResult:
        """Run evaluation on a single item."""
        if self.config.mode == "giant":
            return await self._run_giant(item)
        elif self.config.mode == "thumbnail":
            return await self._run_thumbnail(item)
        else:
            return await self._run_patch(item)

    async def _run_giant(self, item: BenchmarkItem) -> BenchmarkResult:
        """Run GIANT navigation agent."""
        ...

    async def _run_thumbnail(self, item: BenchmarkItem) -> BenchmarkResult:
        """Run thumbnail-only baseline."""
        ...

    async def _run_patch(self, item: BenchmarkItem) -> BenchmarkResult:
        """Run random patch baseline."""
        ...

    def _select_majority_prediction(
        self,
        predictions: list[str],
        labels: list[int | None],
    ) -> tuple[str, int | None]:
        """Select final prediction via majority voting."""
        ...
```

**Files to extract from:**
- `_run_single_item()` (lines 650-678)
- `_build_item_result()` (lines 680-705)
- `_run_item_giant()` (lines 707-760)
- `_run_item_thumbnail()` (lines 763-825)
- `_run_item_patch()` (lines 828-915)
- `_majority_vote()` (lines 917-927)
- `_select_majority_prediction()` (lines 929-969)

**Tests to migrate:**
- `tests/unit/eval/test_runner.py::TestMajorityVote`
- `tests/unit/eval/test_runner.py::TestSelectMajorityPrediction`

---

### 3. ResultsPersistence (`persistence.py`)

**Responsibility:** Save results, trajectories, and checkpoints.

```python
@dataclass
class ResultsPersistence:
    """Handles saving evaluation artifacts."""

    results_dir: Path
    run_id: str
    benchmark_name: str
    model_name: str

    def save_results(self, results: EvaluationResults) -> Path:
        """Save full results to JSON."""
        ...

    def save_trajectory(
        self,
        trajectory: Trajectory,
        item_id: str,
        run_idx: int,
    ) -> Path:
        """Save trajectory to JSON."""
        ...

    @staticmethod
    def validate_run_id(run_id: str) -> None:
        """Validate run_id for filesystem safety."""
        ...

    @staticmethod
    def safe_filename_component(value: str) -> str:
        """Sanitize string for use in filenames."""
        ...
```

**Files to extract from:**
- `_save_results()` (lines 1056-1064)
- `_save_trajectory()` (lines 1028-1054)
- `_validate_run_id()` (lines 544-555)
- `_safe_filename_component()` (lines 557-560)

**Tests to migrate:**
- `tests/unit/eval/test_runner.py::TestValidateRunId`
- `tests/unit/eval/test_runner.py::TestSafeFilenameComponent`

---

### 4. EvaluationOrchestrator (refactored `runner.py`)

**Responsibility:** Coordinate loading, execution, metrics, and persistence.

```python
class EvaluationOrchestrator:
    """Orchestrates benchmark evaluation workflow."""

    def __init__(
        self,
        llm_provider: LLMProvider,
        config: EvaluationConfig,
        results_dir: Path,
    ):
        self.llm_provider = llm_provider
        self.config = config
        self.results_dir = results_dir

        # Composed components
        self._executor: ItemExecutor | None = None
        self._persistence: ResultsPersistence | None = None
        self._checkpoint_manager: CheckpointManager | None = None

    def load_benchmark_items(
        self,
        csv_path: Path,
        wsi_root: Path,
        benchmark_name: str,
    ) -> list[BenchmarkItem]:
        """Load items via BenchmarkItemLoader."""
        loader = BenchmarkItemLoader(
            csv_path=csv_path,
            wsi_root=wsi_root,
            benchmark_name=benchmark_name,
            skip_missing_wsis=self.config.skip_missing_wsis,
        )
        return loader.load()

    async def run_benchmark(
        self,
        items: list[BenchmarkItem],
        benchmark_name: str,
        model_name: str,
        run_id: str | None = None,
    ) -> EvaluationResults:
        """Run full benchmark evaluation."""
        ...

    async def _run_pending_items(
        self,
        pending: list[BenchmarkItem],
    ) -> list[BenchmarkResult]:
        """Execute items with concurrency control."""
        ...

    async def _run_worker(
        self,
        queue: asyncio.Queue[BenchmarkItem],
        results: list[BenchmarkResult],
        budget_state: dict[str, Any],
    ) -> None:
        """Worker coroutine for concurrent execution."""
        ...
```

**Reduced to ~200 lines** by delegating to composed components.

---

## Migration Strategy

### Phase 1: Extract ResultsPersistence (Lowest Coupling)

1. Create `src/giant/eval/persistence.py`
2. Move `_save_results()`, `_save_trajectory()`, `_validate_run_id()`, `_safe_filename_component()`
3. Update `BenchmarkRunner` to use `ResultsPersistence`
4. Run tests, ensure 100% pass
5. Commit: `refactor(eval): extract ResultsPersistence from BenchmarkRunner`

### Phase 2: Extract BenchmarkItemLoader

1. Create `src/giant/eval/loader.py`
2. Move CSV loading and parsing functions
3. Update `BenchmarkRunner` to use `BenchmarkItemLoader`
4. Run tests, ensure 100% pass
5. Commit: `refactor(eval): extract BenchmarkItemLoader from BenchmarkRunner`

### Phase 3: Extract ItemExecutor

1. Create `src/giant/eval/executor.py`
2. Move item execution and voting functions
3. Update `BenchmarkRunner` to use `ItemExecutor`
4. Run tests, ensure 100% pass
5. Commit: `refactor(eval): extract ItemExecutor from BenchmarkRunner`

### Phase 4: Rename and Finalize

1. Rename `BenchmarkRunner` to `EvaluationOrchestrator`
2. Add deprecation alias: `BenchmarkRunner = EvaluationOrchestrator`
3. Update imports across codebase
4. Update documentation
5. Commit: `refactor(eval): rename BenchmarkRunner to EvaluationOrchestrator`

---

## API Compatibility

### Breaking Changes

The refactor will change internal structure but preserve the public API:

```python
# BEFORE (still works with deprecation warning)
from giant.eval.runner import BenchmarkRunner
runner = BenchmarkRunner(llm_provider, config, results_dir)
items = runner.load_benchmark_items(csv_path, wsi_root, benchmark_name)
results = await runner.run_benchmark(items, benchmark_name, model_name)

# AFTER (preferred)
from giant.eval import EvaluationOrchestrator
orchestrator = EvaluationOrchestrator(llm_provider, config, results_dir)
items = orchestrator.load_benchmark_items(csv_path, wsi_root, benchmark_name)
results = await orchestrator.run_benchmark(items, benchmark_name, model_name)
```

### Deprecation Path

1. Add `BenchmarkRunner` as alias with deprecation warning
2. Keep alias for 2 releases
3. Remove alias in major version bump

---

## Test Migration Checklist

Test file: `tests/unit/eval/test_runner.py` (verified 2025-12-31)

| Test Class | Line | Target Module | Status |
|------------|------|---------------|--------|
| `TestLoadBenchmarkItems` | 352 | `loader.py` | Pending |
| `TestResolveWsiPath` | 107 | `loader.py` | Pending |
| `TestWsiNotFound` | 730 | `loader.py` | Pending |
| `TestTruthLabelParsing` | 207 | `loader.py` | Pending |
| `TestMajorityVote` | 240 | `executor.py` | Pending |
| `TestSelectMajorityPrediction` | 737 | `executor.py` | Pending |
| `TestValidateRunId` | 700 | `persistence.py` | Pending |
| `TestSafeFilenameComponent` | 718 | `persistence.py` | Pending |

---

## Acceptance Criteria

- [ ] All 858 unit tests pass
- [ ] No public API changes (deprecation alias in place)
- [ ] Each extracted class has focused responsibility (<200 lines)
- [ ] `EvaluationOrchestrator` is <300 lines
- [ ] Test coverage remains >90%
- [ ] mypy and ruff checks pass
- [ ] Documentation updated

---

## When to Implement

Trigger conditions:
1. Before adding new evaluation modes (e.g., "region-of-interest" mode)
2. When onboarding new developers who need to understand evaluation
3. If test coverage drops below 90%
4. If modifying evaluation logic for new benchmarks

**Current assessment:** Not urgent. Logic is correct and well-tested.
