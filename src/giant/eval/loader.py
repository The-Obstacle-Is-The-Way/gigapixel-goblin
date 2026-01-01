"""Benchmark item loading utilities for evaluation (Spec-10)."""

from __future__ import annotations

import ast
import csv
import json
from dataclasses import dataclass
from pathlib import Path

from giant.data.schemas import BENCHMARK_TASKS, BenchmarkItem
from giant.eval.wsi_resolver import WSIPathResolver
from giant.utils.logging import get_logger

logger = get_logger(__name__)

_PANDA_TRUTH_LABEL_MIN = 0
_PANDA_TRUTH_LABEL_MAX = 5


@dataclass(frozen=True)
class BenchmarkItemLoader:
    """Load and validate MultiPathQA benchmark items from CSV."""

    csv_path: Path
    wsi_resolver: WSIPathResolver
    benchmark_name: str
    skip_missing_wsis: bool = False

    @staticmethod
    def validate_csv_schema(reader: csv.DictReader[str], csv_path: Path) -> None:
        required_columns = {"benchmark_name", "image_path", "answer"}
        fieldnames = set(reader.fieldnames or [])
        missing_columns = sorted(required_columns - fieldnames)
        if missing_columns:
            raise ValueError(
                "Missing required CSV columns: "
                f"{', '.join(missing_columns)} (file={csv_path})"
            )

    @staticmethod
    def parse_options(options_str: str) -> list[str]:
        """Parse the MultiPathQA `options` field into a list of strings.

        MultiPathQA stores options as either:
        - JSON list: ["A", "B"]
        - Python literal list: ['A', 'B']  (common in the released CSV)
        - Pipe-delimited string: A|B (legacy / test fixtures)

        Raises:
            ValueError: If options cannot be parsed into a list.
        """
        text = options_str.strip()
        if not text:
            return []

        try:
            parsed: object = json.loads(text)
        except json.JSONDecodeError:
            try:
                parsed = ast.literal_eval(text)
            except (ValueError, SyntaxError) as e:
                if "|" in text:
                    parsed = [part.strip() for part in text.split("|")]
                else:
                    raise ValueError(
                        f"Unparseable options field: {options_str!r}"
                    ) from e

        if isinstance(parsed, tuple):
            parsed = list(parsed)
        if not isinstance(parsed, list):
            raise ValueError(
                f"Options must be a list, got {type(parsed).__name__}: {options_str!r}"
            )

        cleaned = [str(opt).strip() for opt in parsed]
        return [opt for opt in cleaned if opt]

    @staticmethod
    def inject_options(prompt: str, options: list[str]) -> str:
        formatted_options = "\n".join(
            f"{i}. {opt}" for i, opt in enumerate(options, start=1)
        )

        if "{options}" in prompt:
            return prompt.replace("{options}", formatted_options)

        return (
            f"{prompt}\n\n"
            f"Select from the following options:\n{formatted_options}\n\n"
            "Please respond with the option number (1-based index)."
        )

    @staticmethod
    def validate_truth_label_int(
        label: int,
        *,
        benchmark_name: str,
        options: list[str] | None,
    ) -> None:
        benchmark_name_lower = benchmark_name.strip().lower()

        if benchmark_name_lower == "panda":
            if not _PANDA_TRUTH_LABEL_MIN <= label <= _PANDA_TRUTH_LABEL_MAX:
                raise ValueError(
                    "PANDA truth label must be ISUP grade "
                    f"{_PANDA_TRUTH_LABEL_MIN}-{_PANDA_TRUTH_LABEL_MAX}, got {label}"
                )
            return

        if options is not None and not 1 <= label <= len(options):
            raise ValueError(f"Truth label {label} out of range 1..{len(options)}")

        task_info = BENCHMARK_TASKS.get(benchmark_name_lower)
        classes = task_info.get("classes") if task_info else None
        if isinstance(classes, int) and not 1 <= label <= classes:
            raise ValueError(
                f"Truth label {label} out of range 1..{classes} for "
                f"benchmark {benchmark_name_lower}"
            )

    @classmethod
    def parse_truth_label(
        cls,
        answer: str,
        benchmark_name: str,
        options: list[str] | None,
    ) -> int:
        """Parse truth label from CSV answer field.

        Conventions:
        - Integer strings: direct conversion (1-based for options).
        - String labels (GTEx): find index in options + 1.
        - PANDA: ISUP grade 0-5.
        """
        answer = answer.strip()
        if not answer:
            raise ValueError("Empty truth label")

        # Try integer conversion first
        try:
            label = int(answer)
        except ValueError:
            label = None

        if label is not None:
            cls.validate_truth_label_int(
                label,
                benchmark_name=benchmark_name,
                options=options,
            )
            return label

        # GTEx: string label to index
        if options:
            for i, opt in enumerate(options, start=1):
                if opt == answer:
                    return i

            answer_lower = answer.lower()
            for i, opt in enumerate(options, start=1):
                if opt.lower() == answer_lower:
                    return i

        raise ValueError(
            f"Could not parse truth label {answer!r} for benchmark {benchmark_name!r}"
        )

    def load(self) -> list[BenchmarkItem]:
        """Load benchmark items from MultiPathQA CSV."""
        if not self.csv_path.exists():
            raise FileNotFoundError(f"MultiPathQA CSV not found: {self.csv_path}")

        if self.benchmark_name not in BENCHMARK_TASKS:
            raise ValueError(
                f"Unknown benchmark: {self.benchmark_name}. "
                f"Valid options: {list(BENCHMARK_TASKS.keys())}"
            )

        task_info = BENCHMARK_TASKS[self.benchmark_name]
        items: list[BenchmarkItem] = []
        missing_wsis = 0

        with self.csv_path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            self.validate_csv_schema(reader, self.csv_path)

            for row in reader:
                if row.get("benchmark_name") != self.benchmark_name:
                    continue
                is_valid = (row.get("is_valid") or "True").strip().lower()
                if is_valid != "true":
                    continue

                benchmark_id = (
                    row.get("benchmark_id")
                    or row.get("id")  # legacy / test fixtures
                    or row.get("image_path")
                )
                if not benchmark_id:
                    raise ValueError("Missing benchmark_id in CSV row")

                file_id = row.get("file_id") or None

                image_path = row["image_path"]
                try:
                    wsi_path = self.wsi_resolver.resolve(
                        image_path,
                        self.benchmark_name,
                        file_id=file_id,
                    )
                except FileNotFoundError:
                    if self.skip_missing_wsis:
                        missing_wsis += 1
                        continue
                    raise

                options = None
                options_str = (row.get("options", "") or "").strip()
                if options_str:
                    options = self.parse_options(options_str)
                    if not options:
                        options = None

                prompt = row.get("prompt", row.get("question", ""))
                if options:
                    prompt = self.inject_options(prompt, options)

                try:
                    truth_label = self.parse_truth_label(
                        row.get("answer", ""),
                        self.benchmark_name,
                        options,
                    )
                except ValueError as e:
                    row_id = row.get("id", row.get("image_path", "<unknown>"))
                    raise ValueError(
                        f"Invalid truth label for row {row_id!r}: {e}"
                    ) from e

                item = BenchmarkItem(
                    benchmark_name=self.benchmark_name,
                    benchmark_id=benchmark_id,
                    file_id=file_id,
                    image_path=image_path,
                    prompt=prompt,
                    options=options,
                    metric_type=str(task_info["metric"]),
                    truth_label=truth_label,
                    wsi_path=str(wsi_path),
                )
                items.append(item)

        logger.info(
            "Loaded %d items for benchmark %s (skipped %d missing WSIs)",
            len(items),
            self.benchmark_name,
            missing_wsis,
        )
        return items
