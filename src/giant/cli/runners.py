"""CLI runners for inference and benchmarking (Spec-12).

This module provides the execution logic for the CLI commands,
bridging the CLI interface to the core GIANT components.
"""

from __future__ import annotations

import asyncio
import csv
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from giant.data.schemas import BENCHMARK_TASKS
from giant.eval.wsi_resolver import WSIPathResolver
from giant.utils.logging import get_logger

if TYPE_CHECKING:
    from giant.cli.main import Mode, Provider


@dataclass
class InferenceResult:
    """Result from a single inference run."""

    success: bool
    answer: str
    total_cost: float
    total_tokens: int = 0
    trajectory: Any | None = None
    error_message: str | None = None
    runs_answers: list[str] = field(default_factory=list)
    agreement: float = 1.0


@dataclass
class BenchmarkResult:
    """Result from a benchmark run."""

    run_id: str
    results_path: Path
    metrics: dict[str, Any]
    total_cost: float
    n_items: int
    n_errors: int


@dataclass(frozen=True)
class DataCheckResult:
    """Result from `giant check-data` validation."""

    dataset: str
    rows: int
    total: int
    found: int
    missing: int
    missing_paths: list[str] = field(default_factory=list)

    def missing_examples(self, *, limit: int = 20) -> list[str]:
        return self.missing_paths[:limit]

    def format_message(self, *, wsi_root: Path) -> str:
        if self.total == 0:
            return f"No valid rows found for {self.dataset!r} in MultiPathQA.csv."
        if self.missing == 0:
            return (
                f"All WSIs present for {self.dataset}: {self.found}/{self.total} "
                f"under {wsi_root}"
            )
        return (
            f"Missing {self.missing}/{self.total} WSIs for {self.dataset} under "
            f"{wsi_root}"
        )


def check_data(
    *,
    dataset: str,
    csv_path: Path,
    wsi_root: Path,
) -> DataCheckResult:
    """Validate that WSI files referenced by MultiPathQA exist under `wsi_root`."""
    logger = get_logger(__name__)

    if dataset not in BENCHMARK_TASKS:
        raise ValueError(
            f"Unknown dataset {dataset!r}. Valid options: "
            f"{list(BENCHMARK_TASKS.keys())}"
        )

    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"MultiPathQA CSV not found: {csv_path}")

    resolver = WSIPathResolver(Path(wsi_root))

    rows = 0
    targets: set[tuple[str, str | None]] = set()

    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        if reader.fieldnames is None or "image_path" not in reader.fieldnames:
            raise ValueError("MultiPathQA CSV missing required column: image_path")

        for row in reader:
            rows += 1
            if row.get("benchmark_name") != dataset:
                continue
            if row.get("is_valid", "True").lower() != "true":
                continue

            image_path = row.get("image_path")
            if not image_path:
                raise ValueError("Missing image_path in CSV row")
            file_id = row.get("file_id") or None
            targets.add((image_path, file_id))

    missing_paths: list[str] = []
    for image_path, file_id in sorted(targets, key=lambda t: (t[0], t[1] or "")):
        try:
            resolver.resolve(image_path, dataset, file_id=file_id)
        except FileNotFoundError:
            missing_paths.append(image_path)

    total = len(targets)
    missing_paths = sorted(set(missing_paths))
    missing = len(missing_paths)
    found = total - missing

    logger.info(
        "Data check complete: dataset=%s rows=%d total=%d found=%d missing=%d",
        dataset,
        rows,
        total,
        found,
        missing,
    )

    return DataCheckResult(
        dataset=dataset,
        rows=rows,
        total=total,
        found=found,
        missing=missing,
        missing_paths=missing_paths,
    )


def run_single_inference(  # noqa: PLR0913
    *,
    wsi_path: Path,
    question: str,
    mode: Mode,
    provider: Provider,
    model: str,
    max_steps: int,
    strict_font_check: bool = False,
    runs: int,
    budget_usd: float,
    verbose: int,
) -> InferenceResult:
    """Run inference on a single WSI.

    Supports three modes:
    - giant: Full agentic navigation
    - thumbnail: Single thumbnail baseline
    - patch: CLAM segmentation + random patches baseline
    """
    logger = get_logger(__name__)

    # Import here to avoid circular imports
    from giant.cli.main import Mode  # noqa: PLC0415

    logger.info(
        "Running inference",
        wsi=str(wsi_path),
        mode=mode.value,
        runs=runs,
    )

    if mode == Mode.giant:
        return _run_giant_mode(
            wsi_path=wsi_path,
            question=question,
            provider=provider,
            model=model,
            max_steps=max_steps,
            strict_font_check=strict_font_check,
            runs=runs,
            budget_usd=budget_usd,
        )
    elif mode == Mode.thumbnail:
        return _run_thumbnail_mode(
            wsi_path=wsi_path,
            question=question,
            provider=provider,
            model=model,
            runs=runs,
            budget_usd=budget_usd,
        )
    else:  # mode == Mode.patch
        return _run_patch_mode(
            wsi_path=wsi_path,
            question=question,
            provider=provider,
            model=model,
            runs=runs,
            budget_usd=budget_usd,
        )


def _run_giant_mode(  # pragma: no cover  # noqa: PLR0913
    *,
    wsi_path: Path,
    question: str,
    provider: Provider,
    model: str,
    max_steps: int,
    strict_font_check: bool = False,
    runs: int,
    budget_usd: float,
) -> InferenceResult:
    """Run full GIANT agentic navigation."""
    from giant.agent import AgentConfig, GIANTAgent  # noqa: PLC0415
    from giant.llm import create_provider  # noqa: PLC0415

    llm = create_provider(provider.value, model=model)

    async def run_once(*, config: AgentConfig) -> Any:
        agent = GIANTAgent(
            wsi_path=wsi_path,
            question=question,
            llm_provider=llm,
            config=config,
        )
        return await agent.run()

    async def run_all() -> list[Any]:
        results: list[Any] = []
        total = 0.0

        for _i in range(runs):
            remaining_budget = None
            if budget_usd > 0:
                remaining_budget = max(budget_usd - total, 0.0)
                if remaining_budget <= 0:
                    break

            result = await run_once(
                config=AgentConfig(
                    max_steps=max_steps,
                    budget_usd=remaining_budget,
                    strict_font_check=strict_font_check,
                )
            )
            results.append(result)
            total += result.total_cost

            if budget_usd > 0 and total >= budget_usd:
                break

        return results

    all_results = asyncio.run(run_all())
    total_cost = sum(r.total_cost for r in all_results)
    total_tokens = sum(r.total_tokens for r in all_results)

    return _summarize_runs(
        run_results=all_results,
        total_cost=total_cost,
        total_tokens=total_tokens,
    )


def _run_thumbnail_mode(  # pragma: no cover  # noqa: PLR0913
    *,
    wsi_path: Path,
    question: str,
    provider: Provider,
    model: str,
    runs: int,
    budget_usd: float,
) -> InferenceResult:
    """Run single-thumbnail baseline (no navigation)."""
    from giant.core.baselines import (  # noqa: PLC0415
        BaselineRequest,
        encode_image_to_base64,
        run_baseline_answer,
    )
    from giant.llm import create_provider  # noqa: PLC0415
    from giant.wsi import WSIReader  # noqa: PLC0415

    llm = create_provider(provider.value, model=model)

    with WSIReader(wsi_path) as reader:
        thumbnail = reader.get_thumbnail((1024, 1024))

    image_b64, media_type = encode_image_to_base64(thumbnail)
    request = BaselineRequest(
        wsi_path=wsi_path,
        question=question,
        image_base64=image_b64,
        media_type=media_type,
        context_note="This is a whole-slide thumbnail (no navigation).",
    )

    async def run_all() -> list[Any]:
        results: list[Any] = []
        total = 0.0

        for _i in range(runs):
            if budget_usd > 0 and total >= budget_usd:
                break

            result = await run_baseline_answer(llm_provider=llm, request=request)
            results.append(result)
            total += result.total_cost

            if budget_usd > 0 and total >= budget_usd:
                break

        return results

    run_results = asyncio.run(run_all())
    total_cost = sum(r.total_cost for r in run_results)
    total_tokens = sum(r.total_tokens for r in run_results)

    return _summarize_runs(
        run_results=run_results,
        total_cost=total_cost,
        total_tokens=total_tokens,
    )


def _run_patch_mode(  # pragma: no cover  # noqa: PLR0913
    *,
    wsi_path: Path,
    question: str,
    provider: Provider,
    model: str,
    runs: int,
    budget_usd: float,
) -> InferenceResult:
    """Run CLAM-style random patch baseline."""
    from giant.core.baselines import (  # noqa: PLC0415
        BaselineRequest,
        encode_image_to_base64,
        make_patch_collage,
        run_baseline_answer,
    )
    from giant.llm import create_provider  # noqa: PLC0415
    from giant.vision import (  # noqa: PLC0415
        N_PATCHES,
        PATCH_SIZE,
        TissueSegmentor,
        sample_patches,
    )
    from giant.wsi import WSIReader  # noqa: PLC0415

    llm = create_provider(provider.value, model=model)

    with WSIReader(wsi_path) as reader:
        meta = reader.get_metadata()
        thumbnail = reader.get_thumbnail((2048, 2048))

        segmentor = TissueSegmentor()
        mask = segmentor.segment(thumbnail)
        regions = sample_patches(
            mask,
            meta,
            n_patches=N_PATCHES,
            patch_size=PATCH_SIZE,
        )

        patch_images = [
            reader.read_region((r.x, r.y), 0, (r.width, r.height)) for r in regions
        ]

    collage = make_patch_collage(patch_images, patch_size=PATCH_SIZE)
    image_b64, media_type = encode_image_to_base64(collage)
    request = BaselineRequest(
        wsi_path=wsi_path,
        question=question,
        image_base64=image_b64,
        media_type=media_type,
        context_note=(
            f"This image is a montage of {N_PATCHES} random {PATCH_SIZE}x{PATCH_SIZE} "
            "tissue patches sampled from the slide."
        ),
    )

    async def run_all() -> list[Any]:
        results: list[Any] = []
        total = 0.0

        for _i in range(runs):
            if budget_usd > 0 and total >= budget_usd:
                break

            result = await run_baseline_answer(llm_provider=llm, request=request)
            results.append(result)
            total += result.total_cost

            if budget_usd > 0 and total >= budget_usd:
                break

        return results

    run_results = asyncio.run(run_all())
    total_cost = sum(r.total_cost for r in run_results)
    total_tokens = sum(r.total_tokens for r in run_results)

    return _summarize_runs(
        run_results=run_results,
        total_cost=total_cost,
        total_tokens=total_tokens,
    )


def run_benchmark(  # pragma: no cover  # noqa: PLR0913
    *,
    dataset: str,
    csv_path: Path,
    wsi_root: Path,
    output_dir: Path,
    mode: Mode,
    provider: Provider,
    model: str,
    max_steps: int,
    strict_font_check: bool = False,
    runs: int,
    concurrency: int,
    budget_usd: float,
    resume: bool,
    max_items: int,
    skip_missing: bool,
    verbose: int,
) -> BenchmarkResult:
    """Run benchmark evaluation on a dataset."""
    from giant.eval.runner import BenchmarkRunner, EvaluationConfig  # noqa: PLC0415
    from giant.llm import create_provider  # noqa: PLC0415

    if dataset not in BENCHMARK_TASKS:
        raise ValueError(
            f"Unknown dataset {dataset!r}. Valid options: "
            f"{list(BENCHMARK_TASKS.keys())}"
        )

    llm = create_provider(provider.value, model=model)

    config = EvaluationConfig(
        mode=mode.value,
        max_steps=max_steps,
        runs_per_item=runs,
        max_concurrent=concurrency,
        max_items=max_items if max_items > 0 else None,
        skip_missing_wsis=skip_missing,
        budget_usd=budget_usd if budget_usd > 0 else None,
        strict_font_check=strict_font_check,
    )

    runner = BenchmarkRunner(
        llm_provider=llm,
        wsi_root=wsi_root,
        output_dir=output_dir,
        config=config,
    )

    run_id = _build_run_id(
        dataset=dataset,
        mode=mode.value,
        provider=provider.value,
        model=model,
    )
    if not resume:
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        run_id = f"{run_id}_{timestamp}"

    async def run_async() -> Any:
        return await runner.run_benchmark(
            benchmark_name=dataset,
            csv_path=csv_path,
            run_id=run_id,
        )

    result = asyncio.run(run_async())

    return BenchmarkResult(
        run_id=result.run_id,
        results_path=output_dir / f"{result.run_id}_results.json",
        metrics=result.metrics,
        total_cost=result.total_cost_usd,
        n_items=len(result.results),
        n_errors=sum(r.error is not None for r in result.results),
    )


def download_dataset(
    *,
    dataset: str,
    output_dir: Path,
    force: bool,
    verbose: int,
) -> dict[str, str]:
    """Download datasets needed for GIANT.

    Notes:
        - This command downloads *metadata only* from HuggingFace.
        - Whole-slide images are not redistributed on HuggingFace; see
          `docs/DATA_ACQUISITION.md` and `python -m giant.data.tcga`.
    """
    _ = verbose  # logging is configured by the CLI entrypoint
    logger = get_logger(__name__)

    if dataset != "multipathqa":
        raise ValueError(
            f"Unknown dataset {dataset!r}. Only 'multipathqa' is downloadable via "
            "this command. For TCGA helpers, use `python -m giant.data.tcga`."
        )

    from giant.data.download import download_multipathqa_metadata  # noqa: PLC0415

    path = download_multipathqa_metadata(output_dir / "multipathqa", force=force)
    logger.info("Download complete", dataset=dataset, path=str(path))
    return {"dataset": dataset, "path": str(path)}


def _build_run_id(*, dataset: str, mode: str, provider: str, model: str) -> str:
    """Build a deterministic, filesystem-safe run_id for checkpointing."""
    import re  # noqa: PLC0415

    def safe(value: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("._-")
        return cleaned or "x"

    return "_".join(
        [
            safe(dataset),
            safe(mode),
            safe(provider),
            safe(model),
        ]
    )


def _summarize_runs(
    *,
    run_results: list[Any],
    total_cost: float,
    total_tokens: int,
) -> InferenceResult:
    if not run_results:
        return InferenceResult(
            success=False,
            answer="",
            total_cost=total_cost,
            total_tokens=total_tokens,
            trajectory=None,
            error_message="No runs executed",
        )

    candidates = [r for r in run_results if r.success and r.answer]
    if not candidates:
        candidates = [r for r in run_results if r.answer] or run_results

    answers = [r.answer for r in candidates if r.answer]
    final_answer = answers[0] if answers else ""
    agreement = 1.0
    winning = candidates[0]

    if answers:
        counts = Counter(answers)
        max_count = max(counts.values())
        winners = {a for a, c in counts.items() if c == max_count}
        final_answer = next(a for a in answers if a in winners)
        agreement = counts[final_answer] / len(answers)
        winning = next(r for r in candidates if r.answer == final_answer)

    return InferenceResult(
        success=winning.success,
        answer=final_answer,
        total_cost=total_cost,
        total_tokens=total_tokens,
        trajectory=winning.trajectory,
        error_message=winning.error_message,
        runs_answers=answers,
        agreement=agreement,
    )
