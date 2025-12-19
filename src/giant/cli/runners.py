"""CLI runners for inference and benchmarking (Spec-12).

This module provides the execution logic for the CLI commands,
bridging the CLI interface to the core GIANT components.
"""

from __future__ import annotations

import asyncio
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx

from giant.utils.logging import get_logger

if TYPE_CHECKING:
    from giant.cli.main import Mode, Provider


@dataclass
class InferenceResult:
    """Result from a single inference run."""

    success: bool
    answer: str
    total_cost: float
    trajectory: Any | None = None
    error_message: str | None = None
    runs_answers: list[str] = field(default_factory=list)
    agreement: float = 1.0


@dataclass
class BenchmarkResult:
    """Result from a benchmark run."""

    metrics: dict[str, Any]
    total_cost: float
    n_items: int = 0
    n_errors: int = 0


def run_single_inference(  # noqa: PLR0913
    *,
    wsi_path: Path,
    question: str,
    mode: Mode,
    provider: Provider,
    model: str,
    max_steps: int,
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
    runs: int,
    budget_usd: float,
) -> InferenceResult:
    """Run full GIANT agentic navigation."""
    from giant.agent import AgentConfig, GIANTAgent  # noqa: PLC0415
    from giant.llm import create_provider  # noqa: PLC0415

    llm = create_provider(provider.value, model=model)

    async def run_once() -> Any:
        agent = GIANTAgent(
            wsi_path=wsi_path,
            question=question,
            llm_provider=llm,
            config=AgentConfig(max_steps=max_steps),
        )
        return await agent.run()

    # Run multiple times for majority voting
    all_results = []
    total_cost = 0.0

    for _i in range(runs):
        result = asyncio.run(run_once())
        all_results.append(result)
        total_cost += result.total_cost

        if budget_usd > 0 and total_cost >= budget_usd:
            break

    # Majority vote on answers
    answers = [r.answer for r in all_results if r.answer]
    if answers:
        counter = Counter(answers)
        final_answer, count = counter.most_common(1)[0]
        agreement = count / len(answers)
    else:
        final_answer = all_results[0].answer if all_results else ""
        agreement = 1.0

    return InferenceResult(
        success=all_results[0].success if all_results else False,
        answer=final_answer,
        total_cost=total_cost,
        trajectory=all_results[0].trajectory if all_results else None,
        runs_answers=answers,
        agreement=agreement,
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
    import base64  # noqa: PLC0415
    import os  # noqa: PLC0415
    from io import BytesIO  # noqa: PLC0415

    import anthropic  # noqa: PLC0415

    from giant.wsi import WSIReader  # noqa: PLC0415

    # Get thumbnail
    with WSIReader(wsi_path) as reader:
        thumbnail = reader.get_thumbnail((1024, 1024))

    # Encode to base64
    buffer = BytesIO()
    thumbnail.save(buffer, format="PNG")
    image_b64 = base64.b64encode(buffer.getvalue()).decode()

    async def run_once() -> tuple[str, float]:
        # Use SDK directly for simple text generation (not structured agent response)
        client = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

        message = await client.messages.create(
            model=model,
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": image_b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": (
                                f"You are a pathologist examining this whole-slide "
                                f"image thumbnail. {question}\n\n"
                                f"Provide your answer concisely."
                            ),
                        },
                    ],
                }
            ],
        )

        # Extract text response
        answer = message.content[0].text if message.content else ""  # type: ignore[union-attr]
        # Estimate cost (rough approximation)
        input_cost = message.usage.input_tokens * 0.003
        output_cost = message.usage.output_tokens * 0.015
        cost = (input_cost + output_cost) / 1000
        return answer, cost

    # Run multiple times
    all_answers = []
    total_cost = 0.0

    for _ in range(runs):
        answer, cost = asyncio.run(run_once())
        all_answers.append(answer)
        total_cost += cost

        if budget_usd > 0 and total_cost >= budget_usd:
            break

    # Majority vote
    if all_answers:
        counter = Counter(all_answers)
        final_answer, count = counter.most_common(1)[0]
        agreement = count / len(all_answers)
    else:
        final_answer = ""
        agreement = 1.0

    return InferenceResult(
        success=True,
        answer=final_answer,
        total_cost=total_cost,
        runs_answers=all_answers,
        agreement=agreement,
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
    import base64  # noqa: PLC0415
    import os  # noqa: PLC0415
    from io import BytesIO  # noqa: PLC0415

    import anthropic  # noqa: PLC0415

    from giant.vision import TissueSegmentor, sample_patches  # noqa: PLC0415
    from giant.wsi import WSIReader  # noqa: PLC0415

    # Segment tissue and sample patches
    with WSIReader(wsi_path) as reader:
        meta = reader.get_metadata()
        thumbnail = reader.get_thumbnail((2048, 2048))

        segmentor = TissueSegmentor()
        mask = segmentor.segment(thumbnail)
        patches = sample_patches(mask, meta, n_patches=30)

        # Extract patch images
        patch_images = []
        for patch_region in patches[:10]:  # Limit to 10 for context window
            crop = reader.read_region(
                (patch_region.x, patch_region.y),
                0,  # Level 0
                (patch_region.width, patch_region.height),
            )
            buffer = BytesIO()
            crop.save(buffer, format="PNG")
            patch_images.append(base64.b64encode(buffer.getvalue()).decode())

    async def run_once() -> tuple[str, float]:
        # Use SDK directly for simple text generation (not structured agent response)
        client = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

        # Build prompt with multiple patches
        content: list[dict[str, Any]] = []

        for i, img_b64 in enumerate(patch_images):
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": img_b64,
                    },
                }
            )
            content.append({"type": "text", "text": f"Patch {i + 1}:"})

        content.append(
            {
                "type": "text",
                "text": (
                    f"\nThese are {len(patch_images)} random tissue patches from a "
                    f"whole-slide image. {question}\n\nProvide your answer concisely."
                ),
            }
        )

        message = await client.messages.create(
            model=model,
            max_tokens=1024,
            messages=[{"role": "user", "content": content}],  # type: ignore[typeddict-item]
        )

        # Extract text response
        answer = message.content[0].text if message.content else ""  # type: ignore[union-attr]
        # Estimate cost (rough approximation)
        input_cost = message.usage.input_tokens * 0.003
        output_cost = message.usage.output_tokens * 0.015
        cost = (input_cost + output_cost) / 1000
        return answer, cost

    # Run multiple times
    all_answers = []
    total_cost = 0.0

    for _ in range(runs):
        answer, cost = asyncio.run(run_once())
        all_answers.append(answer)
        total_cost += cost

        if budget_usd > 0 and total_cost >= budget_usd:
            break

    # Majority vote
    if all_answers:
        counter = Counter(all_answers)
        final_answer, count = counter.most_common(1)[0]
        agreement = count / len(all_answers)
    else:
        final_answer = ""
        agreement = 1.0

    return InferenceResult(
        success=True,
        answer=final_answer,
        total_cost=total_cost,
        runs_answers=all_answers,
        agreement=agreement,
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

    _ = get_logger(__name__)  # Reserved for future logging

    llm = create_provider(provider.value, model=model)

    config = EvaluationConfig(
        max_steps=max_steps,
        max_concurrent=concurrency,
        max_items=max_items if max_items > 0 else None,
        skip_missing_wsis=skip_missing,
    )

    runner = BenchmarkRunner(
        llm_provider=llm,
        wsi_root=wsi_root,
        output_dir=output_dir,
        config=config,
    )

    async def run_async() -> Any:
        return await runner.run_benchmark(
            benchmark_name=dataset,
            csv_path=csv_path,
            run_id=f"{dataset}_{mode.value}",
        )

    result = asyncio.run(run_async())

    return BenchmarkResult(
        metrics=result.metrics,
        total_cost=result.total_cost,
        n_items=result.n_total,
        n_errors=result.n_errors,
    )


def download_multipathqa(
    *,
    dataset: str,
    output_dir: Path,
    verbose: int,
) -> bool:
    """Download MultiPathQA dataset from HuggingFace.

    Downloads the CSV metadata file, not the actual WSI files
    (which must be obtained from their respective sources).
    """
    logger = get_logger(__name__)

    # HuggingFace dataset URL
    hf_url = "https://huggingface.co/datasets/jnirschl/MultiPathQA/resolve/main/MultiPathQA.csv"

    output_dir.mkdir(parents=True, exist_ok=True)
    multipathqa_dir = output_dir / "multipathqa"
    multipathqa_dir.mkdir(parents=True, exist_ok=True)

    csv_path = multipathqa_dir / "MultiPathQA.csv"

    logger.info("Downloading MultiPathQA.csv", url=hf_url, dest=str(csv_path))

    try:
        with httpx.Client(timeout=60.0, follow_redirects=True) as client:
            response = client.get(hf_url)
            response.raise_for_status()
            csv_path.write_bytes(response.content)

        logger.info(
            "Download complete", path=str(csv_path), size=csv_path.stat().st_size
        )
        return True

    except httpx.HTTPError as e:
        logger.error("Download failed", error=str(e))
        return False
