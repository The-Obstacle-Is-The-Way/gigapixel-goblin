"""Fixtures for WSI integration tests.

These tests require real WSI files. They are skipped if no test file is available.

Test files can be provided via:
1. WSI_TEST_FILE environment variable pointing to a local .svs file
2. Automatic download of OpenSlide test data (if DOWNLOAD_TEST_WSI=1)

The CMU-1-Small-Region.svs file (~10MB) is recommended for CI:
    https://openslide.cs.cmu.edu/download/openslide-testdata/Aperio/CMU-1-Small-Region.svs
"""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path

import pytest

# Skip all tests in this directory if no WSI test file is available
pytestmark = pytest.mark.integration


def get_test_wsi_path() -> Path | None:
    """Get the path to a real WSI test file.

    Returns:
        Path to WSI file if available, None otherwise.
    """
    # Option 1: User-provided path via environment variable
    env_path = os.environ.get("WSI_TEST_FILE")
    if env_path:
        path = Path(env_path)
        if path.exists() and path.suffix.lower() in {".svs", ".ndpi", ".tiff", ".tif"}:
            return path

    # Option 2: Check for pre-downloaded test file in test data directory
    test_data_dir = Path(__file__).parent / "data"
    if test_data_dir.exists():
        for svs_file in test_data_dir.glob("*.svs"):
            return svs_file

    return None


@pytest.fixture(scope="session")
def wsi_test_file() -> Generator[Path, None, None]:
    """Provide path to a real WSI test file.

    Skips the test if no test file is available.

    Usage:
        def test_something(wsi_test_file: Path) -> None:
            with WSIReader(wsi_test_file) as reader:
                ...
    """
    path = get_test_wsi_path()
    if path is None:
        pytest.skip(
            "No WSI test file available. "
            "Set WSI_TEST_FILE environment variable or download test data. "
            "Example: curl -LO https://openslide.cs.cmu.edu/download/"
            "openslide-testdata/Aperio/CMU-1-Small-Region.svs"
        )
    yield path


@pytest.fixture(scope="session")
def wsi_test_file_optional() -> Path | None:
    """Provide path to a real WSI test file, or None if unavailable.

    Unlike wsi_test_file, this does not skip the test if no file is available.
    Useful for tests that want to behave differently based on availability.
    """
    return get_test_wsi_path()
