"""Dataset download utilities.

This module is intentionally minimal for Spec-01:
- It downloads *metadata only* (MultiPathQA.csv) from HuggingFace.
- Whole-slide images (WSIs) are not distributed via HuggingFace and must be
  obtained separately (see Spec-10).

`make download-data` calls this module via `python -m giant.data.download`.
"""

from __future__ import annotations

import logging
from pathlib import Path

from huggingface_hub import hf_hub_download

from giant.config import settings
from giant.utils.logging import configure_logging, get_logger

logger = logging.getLogger(__name__)

MULTIPATHQA_REPO_ID = "tbuckley/MultiPathQA"
MULTIPATHQA_CSV_FILENAME = "MultiPathQA.csv"
DEFAULT_MULTIPATHQA_DIR = Path("data/multipathqa")


def download_multipathqa_metadata(
    output_dir: Path = DEFAULT_MULTIPATHQA_DIR,
    *,
    force: bool = False,
) -> Path:
    """Download MultiPathQA metadata CSV to the local `data/` directory."""
    output_dir.mkdir(parents=True, exist_ok=True)

    token = settings.HUGGINGFACE_TOKEN
    if token is None:
        logger.debug(
            "HUGGINGFACE_TOKEN not set, using anonymous access. "
            "Set token in .env for private/gated datasets."
        )

    csv_path = hf_hub_download(
        repo_id=MULTIPATHQA_REPO_ID,
        filename=MULTIPATHQA_CSV_FILENAME,
        repo_type="dataset",
        local_dir=output_dir,
        force_download=force,
        token=token,
    )
    return Path(csv_path)


def main() -> None:
    """CLI entrypoint for `python -m giant.data.download`."""
    configure_logging()
    logger = get_logger(__name__)

    csv_path = download_multipathqa_metadata()
    logger.info(
        "Downloaded MultiPathQA metadata CSV",
        repo_id=MULTIPATHQA_REPO_ID,
        path=str(csv_path),
    )


if __name__ == "__main__":  # pragma: no cover
    main()
