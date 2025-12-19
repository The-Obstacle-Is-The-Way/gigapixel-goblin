"""Tests for TCGA GDC download helpers."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from giant.data.tcga import (
    GDC_BASE_URL,
    GdcFile,
    _download_gdc_file,
    _fetch_gdc_metadata,
    _format_bytes,
    _read_multipathqa_tcga_mapping,
    estimate_tcga_size,
    main,
)

if TYPE_CHECKING:
    from collections.abc import Iterator


# =============================================================================
# _format_bytes tests
# =============================================================================


class TestFormatBytes:
    """Tests for byte formatting utility."""

    def test_format_gib(self) -> None:
        """Large values display in GiB."""
        assert _format_bytes(1024**3) == "1.00 GiB"
        assert _format_bytes(2 * 1024**3) == "2.00 GiB"
        assert _format_bytes(int(1.5 * 1024**3)) == "1.50 GiB"

    def test_format_mib(self) -> None:
        """Sub-GiB values display in MiB."""
        assert _format_bytes(1024**2) == "1.0 MiB"
        assert _format_bytes(500 * 1024**2) == "500.0 MiB"
        assert _format_bytes(int(0.5 * 1024**2)) == "0.5 MiB"

    def test_format_edge_just_under_gib(self) -> None:
        """Values just under 1 GiB display in MiB."""
        just_under = 1024**3 - 1
        result = _format_bytes(just_under)
        assert "MiB" in result

    def test_format_zero(self) -> None:
        """Zero bytes displays as MiB."""
        assert _format_bytes(0) == "0.0 MiB"


# =============================================================================
# _read_multipathqa_tcga_mapping tests
# =============================================================================


@pytest.fixture
def valid_csv(tmp_path: Path) -> Path:
    """Create a valid MultiPathQA CSV file."""
    csv_path = tmp_path / "MultiPathQA.csv"
    rows = [
        {
            "benchmark_name": "tcga",
            "file_id": "abc123",
            "image_path": "slides/abc.svs",
        },
        {
            "benchmark_name": "tcga_expert_vqa",
            "file_id": "def456",
            "image_path": "slides/def.svs",
        },
        {
            "benchmark_name": "tcga_slidebench",
            "file_id": "ghi789",
            "image_path": "slides/ghi.svs",
        },
        {
            "benchmark_name": "gtex",  # Not TCGA - should be skipped
            "file_id": "skip001",
            "image_path": "slides/skip.tiff",
        },
        {
            "benchmark_name": "panda",  # Not TCGA - should be skipped
            "file_id": "skip002",
            "image_path": "slides/skip2.tiff",
        },
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["benchmark_name", "file_id", "image_path"]
        )
        writer.writeheader()
        writer.writerows(rows)
    return csv_path


class TestReadMultipathqaTcgaMapping:
    """Tests for CSV parsing."""

    def test_reads_tcga_benchmarks(self, valid_csv: Path) -> None:
        """Parses all TCGA benchmark rows."""
        mapping = _read_multipathqa_tcga_mapping(valid_csv)
        assert len(mapping) == 3
        assert mapping["abc123"] == "slides/abc.svs"
        assert mapping["def456"] == "slides/def.svs"
        assert mapping["ghi789"] == "slides/ghi.svs"

    def test_skips_non_tcga_benchmarks(self, valid_csv: Path) -> None:
        """GTEx and PANDA rows are skipped."""
        mapping = _read_multipathqa_tcga_mapping(valid_csv)
        assert "skip001" not in mapping
        assert "skip002" not in mapping

    def test_duplicate_file_id_same_path_ok(self, tmp_path: Path) -> None:
        """Same file_id with same image_path is allowed (deduplication)."""
        csv_path = tmp_path / "dupe.csv"
        rows = [
            {"benchmark_name": "tcga", "file_id": "abc", "image_path": "x.svs"},
            {
                "benchmark_name": "tcga_expert_vqa",
                "file_id": "abc",
                "image_path": "x.svs",
            },
        ]
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f, fieldnames=["benchmark_name", "file_id", "image_path"]
            )
            writer.writeheader()
            writer.writerows(rows)
        mapping = _read_multipathqa_tcga_mapping(csv_path)
        assert len(mapping) == 1
        assert mapping["abc"] == "x.svs"

    def test_conflicting_image_path_raises(self, tmp_path: Path) -> None:
        """Same file_id with different image_path raises."""
        csv_path = tmp_path / "conflict.csv"
        rows = [
            {"benchmark_name": "tcga", "file_id": "abc", "image_path": "x.svs"},
            {"benchmark_name": "tcga", "file_id": "abc", "image_path": "y.svs"},
        ]
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f, fieldnames=["benchmark_name", "file_id", "image_path"]
            )
            writer.writeheader()
            writer.writerows(rows)
        with pytest.raises(ValueError, match="Conflicting image_path"):
            _read_multipathqa_tcga_mapping(csv_path)

    def test_missing_file_id_raises(self, tmp_path: Path) -> None:
        """Missing file_id raises."""
        csv_path = tmp_path / "missing.csv"
        rows = [
            {"benchmark_name": "tcga", "file_id": "", "image_path": "x.svs"},
        ]
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f, fieldnames=["benchmark_name", "file_id", "image_path"]
            )
            writer.writeheader()
            writer.writerows(rows)
        with pytest.raises(ValueError, match="missing file_id or image_path"):
            _read_multipathqa_tcga_mapping(csv_path)

    def test_missing_image_path_raises(self, tmp_path: Path) -> None:
        """Missing image_path raises."""
        csv_path = tmp_path / "missing.csv"
        rows = [
            {"benchmark_name": "tcga", "file_id": "abc", "image_path": ""},
        ]
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f, fieldnames=["benchmark_name", "file_id", "image_path"]
            )
            writer.writeheader()
            writer.writerows(rows)
        with pytest.raises(ValueError, match="missing file_id or image_path"):
            _read_multipathqa_tcga_mapping(csv_path)

    def test_no_tcga_rows_raises(self, tmp_path: Path) -> None:
        """CSV with no TCGA rows raises."""
        csv_path = tmp_path / "empty.csv"
        rows = [
            {"benchmark_name": "gtex", "file_id": "abc", "image_path": "x.tiff"},
        ]
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f, fieldnames=["benchmark_name", "file_id", "image_path"]
            )
            writer.writeheader()
            writer.writerows(rows)
        with pytest.raises(ValueError, match="No TCGA rows found"):
            _read_multipathqa_tcga_mapping(csv_path)

    def test_strips_whitespace(self, tmp_path: Path) -> None:
        """Whitespace is stripped from file_id and image_path."""
        csv_path = tmp_path / "whitespace.csv"
        rows = [
            {"benchmark_name": "tcga", "file_id": "  abc  ", "image_path": "  x.svs  "},
        ]
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f, fieldnames=["benchmark_name", "file_id", "image_path"]
            )
            writer.writeheader()
            writer.writerows(rows)
        mapping = _read_multipathqa_tcga_mapping(csv_path)
        assert mapping["abc"] == "x.svs"


# =============================================================================
# _fetch_gdc_metadata tests
# =============================================================================


class TestFetchGdcMetadata:
    """Tests for GDC API metadata fetching."""

    def test_fetches_metadata(self) -> None:
        """Successfully fetches and parses GDC response."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": {
                "hits": [
                    {
                        "file_id": "abc123",
                        "file_name": "slide.svs",
                        "file_size": 1000000,
                    },
                    {
                        "file_id": "def456",
                        "file_name": "slide2.svs",
                        "file_size": 2000000,
                    },
                ]
            }
        }

        with patch("giant.data.tcga.httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            files = _fetch_gdc_metadata(["abc123", "def456"])

        assert len(files) == 2
        assert files[0].file_id == "abc123"
        assert files[0].file_name == "slide.svs"
        assert files[0].file_size == 1000000
        assert files[1].file_id == "def456"

    def test_sends_correct_payload(self) -> None:
        """Verifies correct API payload structure."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": {"hits": []}}

        with patch("giant.data.tcga.httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            _fetch_gdc_metadata(["id1", "id2"])

            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert call_args[0][0] == f"{GDC_BASE_URL}/files"
            payload = call_args[1]["json"]
            assert payload["filters"]["content"]["value"] == ["id1", "id2"]
            assert payload["size"] == 2


# =============================================================================
# estimate_tcga_size tests
# =============================================================================


class TestEstimateTcgaSize:
    """Tests for size estimation."""

    def test_estimates_size(self, valid_csv: Path) -> None:
        """Calculates total size from metadata."""
        mock_files = [
            GdcFile("abc123", "a.svs", 1000),
            GdcFile("def456", "b.svs", 2000),
            GdcFile("ghi789", "c.svs", 3000),
        ]

        with patch(
            "giant.data.tcga._fetch_gdc_metadata", return_value=mock_files
        ) as mock_fetch:
            total, files = estimate_tcga_size(valid_csv)

        assert total == 6000
        assert len(files) == 3
        mock_fetch.assert_called_once()


# =============================================================================
# _download_gdc_file tests
# =============================================================================


class TestDownloadGdcFile:
    """Tests for file downloading."""

    def test_skips_existing_file(self, tmp_path: Path) -> None:
        """Skips download if file exists with correct size."""
        file = GdcFile("abc123", "test.svs", 100)
        out_dir = tmp_path / "downloads"
        dest_dir = out_dir / file.file_id
        dest_dir.mkdir(parents=True)
        dest_path = dest_dir / file.file_name
        dest_path.write_bytes(b"x" * 100)

        result = _download_gdc_file(file=file, out_dir=out_dir, reserve_bytes=0)
        assert result == dest_path

    def test_downloads_new_file(self, tmp_path: Path) -> None:
        """Downloads file when not present."""
        file = GdcFile("abc123", "test.svs", 10)
        out_dir = tmp_path / "downloads"
        file_content = b"x" * 10

        def iter_bytes_mock(chunk_size: int) -> Iterator[bytes]:
            yield file_content

        mock_response = MagicMock()
        mock_response.iter_bytes = iter_bytes_mock
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("giant.data.tcga.httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.stream.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = _download_gdc_file(file=file, out_dir=out_dir, reserve_bytes=0)

        assert result == out_dir / file.file_id / file.file_name
        assert result.read_bytes() == file_content

    def test_raises_on_insufficient_space(self, tmp_path: Path) -> None:
        """Raises when not enough disk space."""
        file = GdcFile("abc123", "test.svs", 1000)
        out_dir = tmp_path / "downloads"
        out_dir.mkdir(parents=True)

        # Request impossibly large reserve
        huge_reserve = 10**18  # 1 exabyte

        with pytest.raises(RuntimeError, match="Not enough free space"):
            _download_gdc_file(file=file, out_dir=out_dir, reserve_bytes=huge_reserve)

    def test_raises_on_size_mismatch(self, tmp_path: Path) -> None:
        """Raises when downloaded size doesn't match expected."""
        file = GdcFile("abc123", "test.svs", 100)  # Expect 100 bytes
        out_dir = tmp_path / "downloads"
        file_content = b"x" * 50  # Only 50 bytes

        def iter_bytes_mock(chunk_size: int) -> Iterator[bytes]:
            yield file_content

        mock_response = MagicMock()
        mock_response.iter_bytes = iter_bytes_mock
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("giant.data.tcga.httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.stream.return_value = mock_response
            mock_client_class.return_value = mock_client

            with pytest.raises(RuntimeError, match="Downloaded size mismatch"):
                _download_gdc_file(file=file, out_dir=out_dir, reserve_bytes=0)

    def test_removes_partial_on_error(self, tmp_path: Path) -> None:
        """Cleans up .part file on size mismatch."""
        file = GdcFile("abc123", "test.svs", 100)
        out_dir = tmp_path / "downloads"
        file_content = b"x" * 50

        def iter_bytes_mock(chunk_size: int) -> Iterator[bytes]:
            yield file_content

        mock_response = MagicMock()
        mock_response.iter_bytes = iter_bytes_mock
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("giant.data.tcga.httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.stream.return_value = mock_response
            mock_client_class.return_value = mock_client

            with pytest.raises(RuntimeError):
                _download_gdc_file(file=file, out_dir=out_dir, reserve_bytes=0)

        part_path = out_dir / file.file_id / f"{file.file_name}.part"
        assert not part_path.exists()

    def test_removes_existing_partial_before_download(self, tmp_path: Path) -> None:
        """Removes stale .part file before starting download."""
        file = GdcFile("abc123", "test.svs", 10)
        out_dir = tmp_path / "downloads"
        dest_dir = out_dir / file.file_id
        dest_dir.mkdir(parents=True)
        part_path = dest_dir / f"{file.file_name}.part"
        part_path.write_bytes(b"stale data")

        file_content = b"x" * 10

        def iter_bytes_mock(chunk_size: int) -> Iterator[bytes]:
            yield file_content

        mock_response = MagicMock()
        mock_response.iter_bytes = iter_bytes_mock
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("giant.data.tcga.httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.stream.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = _download_gdc_file(file=file, out_dir=out_dir, reserve_bytes=0)

        assert result.read_bytes() == file_content


class TestDownloadGdcFileSecurity:
    """Tests for security hardening of downloads."""

    def test_raises_on_traversal_filename(self, tmp_path: Path) -> None:
        """Raises when file_name contains traversal characters."""
        file = GdcFile("abc123", "../evil.svs", 100)
        out_dir = tmp_path / "downloads"
        out_dir.mkdir(parents=True)

        with pytest.raises(ValueError, match="Invalid file_name"):
            _download_gdc_file(file=file, out_dir=out_dir, reserve_bytes=0)

    def test_raises_on_absolute_path(self, tmp_path: Path) -> None:
        """Raises when file_name is an absolute path."""
        file = GdcFile("abc123", "/etc/passwd", 100)
        out_dir = tmp_path / "downloads"
        out_dir.mkdir(parents=True)

        with pytest.raises(ValueError, match="Invalid file_name"):
            _download_gdc_file(file=file, out_dir=out_dir, reserve_bytes=0)

    def test_raises_on_subdir(self, tmp_path: Path) -> None:
        """Raises when file_name contains path separators."""
        file = GdcFile("abc123", "subdir/test.svs", 100)
        out_dir = tmp_path / "downloads"
        out_dir.mkdir(parents=True)

        with pytest.raises(ValueError, match="Invalid file_name"):
            _download_gdc_file(file=file, out_dir=out_dir, reserve_bytes=0)


# =============================================================================
# main() CLI tests
# =============================================================================


class TestMainCli:
    """Tests for CLI entry point."""

    def test_estimate_command(
        self, valid_csv: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test estimate subcommand."""
        mock_files = [
            GdcFile("abc123", "a.svs", 1024**3),  # 1 GiB
            GdcFile("def456", "b.svs", 500 * 1024**2),  # 500 MiB
        ]

        with (
            patch("giant.data.tcga._fetch_gdc_metadata", return_value=mock_files),
            patch(
                "sys.argv",
                ["tcga", "estimate", "--csv-path", str(valid_csv), "--top", "2"],
            ),
        ):
            main()

        captured = capsys.readouterr()
        assert "Total TCGA slides: 2" in captured.out
        assert "1.49 GiB" in captured.out  # Total: 1 GiB + 500 MiB
        assert "Smallest:" in captured.out
        assert "Largest:" in captured.out

    def test_estimate_command_no_top(
        self, valid_csv: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test estimate with --top 0."""
        mock_files = [GdcFile("abc123", "a.svs", 1024**3)]

        with (
            patch("giant.data.tcga._fetch_gdc_metadata", return_value=mock_files),
            patch(
                "sys.argv",
                ["tcga", "estimate", "--csv-path", str(valid_csv), "--top", "0"],
            ),
        ):
            main()

        captured = capsys.readouterr()
        assert "Total TCGA slides: 1" in captured.out
        assert "Smallest:" not in captured.out

    def test_download_dry_run(
        self, valid_csv: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test download --dry-run."""
        mock_files = [
            GdcFile("abc123", "a.svs", 1000),
            GdcFile("def456", "b.svs", 2000),
        ]
        out_dir = tmp_path / "out"

        with (
            patch("giant.data.tcga._fetch_gdc_metadata", return_value=mock_files),
            patch(
                "sys.argv",
                [
                    "tcga",
                    "download",
                    "--csv-path",
                    str(valid_csv),
                    "--out-dir",
                    str(out_dir),
                    "--smallest",
                    "1",
                    "--dry-run",
                ],
            ),
        ):
            main()

        captured = capsys.readouterr()
        assert "Planned downloads: 1" in captured.out
        assert not out_dir.exists()

    def test_download_smallest_zero_raises(self, valid_csv: Path) -> None:
        """Test download with --smallest 0 raises."""
        mock_files = [GdcFile("abc123", "a.svs", 1000)]

        with (
            patch("giant.data.tcga._fetch_gdc_metadata", return_value=mock_files),
            patch(
                "sys.argv",
                ["tcga", "download", "--csv-path", str(valid_csv), "--smallest", "0"],
            ),
            pytest.raises(SystemExit, match="--smallest must be >= 1"),
        ):
            main()

    def test_download_executes(self, valid_csv: Path, tmp_path: Path) -> None:
        """Test actual download (mocked HTTP)."""
        mock_files = [GdcFile("abc123", "a.svs", 10)]
        out_dir = tmp_path / "out"
        file_content = b"x" * 10

        def iter_bytes_mock(chunk_size: int) -> Iterator[bytes]:
            yield file_content

        mock_response = MagicMock()
        mock_response.iter_bytes = iter_bytes_mock
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with (
            patch("giant.data.tcga._fetch_gdc_metadata", return_value=mock_files),
            patch("giant.data.tcga.httpx.Client") as mock_client_class,
            patch(
                "sys.argv",
                [
                    "tcga",
                    "download",
                    "--csv-path",
                    str(valid_csv),
                    "--out-dir",
                    str(out_dir),
                    "--smallest",
                    "1",
                ],
            ),
        ):
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.stream.return_value = mock_response
            mock_client_class.return_value = mock_client

            main()

        downloaded = out_dir / "abc123" / "a.svs"
        assert downloaded.exists()
        assert downloaded.read_bytes() == file_content


class TestGdcFile:
    """Tests for GdcFile dataclass."""

    def test_frozen(self) -> None:
        """GdcFile is immutable."""
        f = GdcFile("id", "name", 100)
        with pytest.raises(AttributeError):  # Frozen dataclass
            f.file_id = "new"  # type: ignore[misc]

    def test_equality(self) -> None:
        """GdcFile supports equality."""
        f1 = GdcFile("id", "name", 100)
        f2 = GdcFile("id", "name", 100)
        f3 = GdcFile("other", "name", 100)
        assert f1 == f2
        assert f1 != f3
