from pathlib import Path

import pytest

from giant.cli.main import Mode, Provider
from giant.cli.runners import run_benchmark


def test_run_benchmark_invalid_dataset_fail_fast():
    """BUG-033: run_benchmark should fail fast on invalid dataset."""
    with pytest.raises(ValueError, match="Unknown dataset 'invalid_ds'"):
        run_benchmark(
            dataset="invalid_ds",
            csv_path=Path("dummy.csv"),
            wsi_root=Path("dummy_root"),
            output_dir=Path("dummy_out"),
            mode=Mode.giant,
            provider=Provider.openai,
            model="gpt-5.2",
            max_steps=5,
            runs=1,
            concurrency=1,
            budget_usd=0.0,
            resume=False,
            max_items=0,
            skip_missing=True,
            verbose=0,
        )
