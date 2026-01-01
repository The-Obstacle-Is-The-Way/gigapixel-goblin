"""Tests for giant.eval.wsi_resolver module (Spec-10).

These tests verify the WSIPathResolver class that handles
resolving WSI paths under a user-provided wsi_root directory.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from giant.eval.wsi_resolver import WSIPathResolver


@pytest.fixture
def resolver(tmp_path: Path) -> WSIPathResolver:
    """Create a WSIPathResolver with a temp wsi_root."""
    wsi_root = tmp_path / "wsi"
    wsi_root.mkdir()
    return WSIPathResolver(wsi_root=wsi_root)


class TestWsiSubdirForBenchmark:
    """Tests for WSIPathResolver.wsi_subdir_for_benchmark static method."""

    def test_tcga_benchmarks_return_tcga(self) -> None:
        """Verify TCGA-related benchmarks map to 'tcga' subdir."""
        assert WSIPathResolver.wsi_subdir_for_benchmark("tcga") == "tcga"
        assert WSIPathResolver.wsi_subdir_for_benchmark("tcga_expert_vqa") == "tcga"
        assert WSIPathResolver.wsi_subdir_for_benchmark("tcga_slidebench") == "tcga"

    def test_other_benchmarks_return_as_is(self) -> None:
        """Verify other benchmarks return their name as-is."""
        assert WSIPathResolver.wsi_subdir_for_benchmark("panda") == "panda"
        assert WSIPathResolver.wsi_subdir_for_benchmark("gtex") == "gtex"


class TestValidateFileId:
    """Tests for WSIPathResolver._validate_file_id static method."""

    def test_accepts_valid_file_id(self, resolver: WSIPathResolver) -> None:
        """Verify valid file IDs pass validation."""
        # Should not raise
        resolver._validate_file_id("uuid-123-456")
        resolver._validate_file_id("abc.def")
        resolver._validate_file_id("simple")

    def test_rejects_absolute_path(self, resolver: WSIPathResolver) -> None:
        """Verify absolute paths are rejected."""
        with pytest.raises(ValueError, match="Invalid file_id"):
            resolver._validate_file_id("/etc/passwd")

    def test_rejects_path_traversal(self, resolver: WSIPathResolver) -> None:
        """Verify path traversal is rejected."""
        with pytest.raises(ValueError, match="Invalid file_id"):
            resolver._validate_file_id("../escape")

    def test_rejects_subdirectory(self, resolver: WSIPathResolver) -> None:
        """Verify subdirectory paths are rejected."""
        with pytest.raises(ValueError, match="Invalid file_id"):
            resolver._validate_file_id("subdir/file")


class TestResolve:
    """Tests for WSIPathResolver.resolve method."""

    def test_finds_direct_path(self, resolver: WSIPathResolver) -> None:
        """Verify file directly under wsi_root is found."""
        (resolver.wsi_root / "slide.svs").write_text("slide")
        resolved = resolver.resolve("slide.svs", "tcga")
        assert resolved == resolver.wsi_root / "slide.svs"

    def test_finds_benchmark_subdir_path(self, resolver: WSIPathResolver) -> None:
        """Verify file under benchmark subdir is found."""
        (resolver.wsi_root / "tcga").mkdir()
        (resolver.wsi_root / "tcga" / "slide.svs").write_text("slide")
        resolved = resolver.resolve("slide.svs", "tcga")
        assert resolved == resolver.wsi_root / "tcga" / "slide.svs"

    def test_rejects_absolute_image_path(self, resolver: WSIPathResolver) -> None:
        """Verify absolute image_path is rejected."""
        with pytest.raises(ValueError, match="absolute paths are not allowed"):
            resolver.resolve("/etc/passwd", "tcga")

    def test_rejects_path_traversal(self, resolver: WSIPathResolver) -> None:
        """Verify path traversal is rejected."""
        with pytest.raises(ValueError, match="path traversal is not allowed"):
            resolver.resolve("../secret.svs", "tcga")

    def test_raises_file_not_found(self, resolver: WSIPathResolver) -> None:
        """Verify FileNotFoundError when WSI not found."""
        with pytest.raises(FileNotFoundError, match="WSI not found"):
            resolver.resolve("nonexistent.svs", "tcga")


class TestResolveFileIdDir:
    """Tests for WSIPathResolver._try_resolve_file_id_dir method."""

    def test_finds_file_in_file_id_dir(self, resolver: WSIPathResolver) -> None:
        """Verify file is found in file_id subdirectory."""
        file_id = "uuid-123"
        (resolver.wsi_root / "tcga" / file_id).mkdir(parents=True)
        (resolver.wsi_root / "tcga" / file_id / "slide.svs").write_text("slide")

        resolved = resolver.resolve("slide.svs", "tcga", file_id=file_id)
        assert resolved == resolver.wsi_root / "tcga" / file_id / "slide.svs"

    def test_finds_file_with_uuid_suffix(self, resolver: WSIPathResolver) -> None:
        """Verify file with UUID suffix is matched by stem."""
        file_id = "uuid-456"
        (resolver.wsi_root / "tcga" / file_id).mkdir(parents=True)
        # File has additional UUID in name
        (resolver.wsi_root / "tcga" / file_id / "slide.uuid-789.svs").write_text(
            "slide"
        )

        resolved = resolver.resolve("slide.svs", "tcga", file_id=file_id)
        assert resolved == resolver.wsi_root / "tcga" / file_id / "slide.uuid-789.svs"

    def test_multiple_candidates_with_prefix_match(
        self, resolver: WSIPathResolver
    ) -> None:
        """Verify prefix matching when multiple candidates exist."""
        file_id = "uuid-multi"
        (resolver.wsi_root / "tcga" / file_id).mkdir(parents=True)
        # Create multiple .svs files
        (resolver.wsi_root / "tcga" / file_id / "slide.uuid-a.svs").write_text("a")
        (resolver.wsi_root / "tcga" / file_id / "other.uuid-b.svs").write_text("b")

        resolved = resolver.resolve("slide.svs", "tcga", file_id=file_id)
        assert "slide" in resolved.name

    def test_file_id_dir_directly_under_wsi_root(
        self, resolver: WSIPathResolver
    ) -> None:
        """Verify file_id dir can be directly under wsi_root."""
        file_id = "uuid-direct"
        (resolver.wsi_root / file_id).mkdir()
        (resolver.wsi_root / file_id / "slide.svs").write_text("slide")

        resolved = resolver.resolve("slide.svs", "tcga", file_id=file_id)
        assert resolved == resolver.wsi_root / file_id / "slide.svs"


class TestResolveUuidSuffixedFilename:
    """Tests for UUID-suffixed filename resolution."""

    def test_finds_uuid_suffixed_filename(self, resolver: WSIPathResolver) -> None:
        """Verify UUID-suffixed file is found by stem matching."""
        (resolver.wsi_root / "tcga").mkdir()
        # File has UUID suffix: TCGA-XX-XXXX.uuid123.svs
        (resolver.wsi_root / "tcga" / "TCGA-XX-XXXX.uuid123.svs").write_text("slide")

        resolved = resolver.resolve("TCGA-XX-XXXX.svs", "tcga")
        assert resolved == resolver.wsi_root / "tcga" / "TCGA-XX-XXXX.uuid123.svs"

    def test_raises_on_ambiguous_matches(self, resolver: WSIPathResolver) -> None:
        """Verify error when multiple UUID-suffixed files match."""
        (resolver.wsi_root / "tcga").mkdir()
        (resolver.wsi_root / "tcga" / "slide.uuid-a.svs").write_text("a")
        (resolver.wsi_root / "tcga" / "slide.uuid-b.svs").write_text("b")

        with pytest.raises(FileNotFoundError, match="ambiguous"):
            resolver.resolve("slide.svs", "tcga")


class TestResolveDicomDirectory:
    """Tests for DICOM directory resolution."""

    def test_finds_dicom_directory(self, resolver: WSIPathResolver) -> None:
        """Verify DICOM directory is resolved from .tiff image_path."""
        from pydicom.dataset import Dataset, FileMetaDataset
        from pydicom.uid import ExplicitVRLittleEndian, generate_uid

        dicom_dir = resolver.wsi_root / "gtex" / "GTEX-TEST"
        dicom_dir.mkdir(parents=True)

        series_uid = generate_uid()

        def write_dicom(path: Path) -> None:
            file_meta = FileMetaDataset()
            file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
            file_meta.MediaStorageSOPClassUID = generate_uid()
            file_meta.MediaStorageSOPInstanceUID = generate_uid()
            file_meta.ImplementationClassUID = generate_uid()

            ds = Dataset()
            ds.file_meta = file_meta
            ds.SeriesInstanceUID = series_uid
            ds.SOPClassUID = file_meta.MediaStorageSOPClassUID
            ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
            ds.save_as(path, enforce_file_format=True)

        write_dicom(dicom_dir / "a.dcm")
        write_dicom(dicom_dir / "b.dcm")

        resolved = resolver.resolve("GTEX-TEST.tiff", "gtex")
        assert resolved.parent == dicom_dir
        assert resolved.suffix == ".dcm"

    def test_raises_on_multiple_series(self, resolver: WSIPathResolver) -> None:
        """Verify error when multiple DICOM series exist in directory."""
        from pydicom.dataset import Dataset, FileMetaDataset
        from pydicom.uid import ExplicitVRLittleEndian, generate_uid

        dicom_dir = resolver.wsi_root / "gtex" / "GTEX-MULTI"
        dicom_dir.mkdir(parents=True)

        def write_dicom(path: Path, *, series_uid: str) -> None:
            file_meta = FileMetaDataset()
            file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
            file_meta.MediaStorageSOPClassUID = generate_uid()
            file_meta.MediaStorageSOPInstanceUID = generate_uid()
            file_meta.ImplementationClassUID = generate_uid()

            ds = Dataset()
            ds.file_meta = file_meta
            ds.SeriesInstanceUID = series_uid
            ds.SOPClassUID = file_meta.MediaStorageSOPClassUID
            ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
            ds.save_as(path, enforce_file_format=True)

        # Two different series
        write_dicom(dicom_dir / "a.dcm", series_uid=generate_uid())
        write_dicom(dicom_dir / "b.dcm", series_uid=generate_uid())

        with pytest.raises(ValueError, match="multiple DICOM series"):
            resolver.resolve("GTEX-MULTI.tiff", "gtex")

    def test_raises_on_missing_series_uid(self, resolver: WSIPathResolver) -> None:
        """Verify error when DICOM file lacks SeriesInstanceUID."""
        from pydicom.dataset import Dataset, FileMetaDataset
        from pydicom.uid import ExplicitVRLittleEndian, generate_uid

        dicom_dir = resolver.wsi_root / "gtex" / "GTEX-NOUID"
        dicom_dir.mkdir(parents=True)

        file_meta = FileMetaDataset()
        file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
        file_meta.MediaStorageSOPClassUID = generate_uid()
        file_meta.MediaStorageSOPInstanceUID = generate_uid()
        file_meta.ImplementationClassUID = generate_uid()

        ds = Dataset()
        ds.file_meta = file_meta
        # Deliberately omit SeriesInstanceUID
        ds.SOPClassUID = file_meta.MediaStorageSOPClassUID
        ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
        ds.save_as(dicom_dir / "no_series.dcm", enforce_file_format=True)

        with pytest.raises(ValueError, match="SeriesInstanceUID"):
            resolver.resolve("GTEX-NOUID.tiff", "gtex")

    def test_raises_on_invalid_dicom(self, resolver: WSIPathResolver) -> None:
        """Verify error when DICOM file is invalid."""
        dicom_dir = resolver.wsi_root / "gtex" / "GTEX-INVALID"
        dicom_dir.mkdir(parents=True)

        # Write invalid DICOM (just some random bytes)
        (dicom_dir / "invalid.dcm").write_bytes(b"not a valid dicom file")

        with pytest.raises(ValueError, match="Invalid DICOM"):
            resolver.resolve("GTEX-INVALID.tiff", "gtex")


class TestWSIPathResolverIsFrozen:
    """Tests for WSIPathResolver immutability."""

    def test_is_frozen(self, resolver: WSIPathResolver) -> None:
        """Verify WSIPathResolver is frozen (immutable)."""
        with pytest.raises(AttributeError):
            resolver.wsi_root = Path("/other")  # type: ignore[misc]
