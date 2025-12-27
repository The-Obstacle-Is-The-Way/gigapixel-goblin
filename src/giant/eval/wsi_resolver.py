"""WSI path resolution helpers for MultiPathQA (Spec-10).

Centralizes the logic for resolving `image_path` entries from MultiPathQA.csv
into local WSI files under a user-provided `--wsi-root`.

This is shared by:
- the evaluation runner (Spec-10), and
- CLI data validation helpers (Spec-12).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WSIPathResolver:
    """Resolve MultiPathQA `image_path` entries under a `wsi_root` directory."""

    wsi_root: Path

    @staticmethod
    def wsi_subdir_for_benchmark(benchmark_name: str) -> str:
        """Map a benchmark name to the expected WSI subdirectory under wsi_root."""
        if benchmark_name in {"tcga", "tcga_expert_vqa", "tcga_slidebench"}:
            return "tcga"
        return benchmark_name

    @staticmethod
    def _validate_file_id(file_id: str) -> None:
        file_id_path = Path(file_id)
        if (
            file_id_path.is_absolute()
            or ".." in file_id_path.parts
            or file_id_path.name != file_id
        ):
            raise ValueError(
                f"Invalid file_id {file_id!r}: must be a simple filename "
                "(no path traversal)."
            )

    def _try_resolve_file_id_dir(
        self,
        *,
        image_rel: Path,
        wsi_subdir: str,
        file_id: str,
    ) -> Path | None:
        """Resolve a WSI from a per-file_id directory (e.g., gdc-client layout)."""
        self._validate_file_id(file_id)

        candidate_dirs = [
            self.wsi_root / wsi_subdir / file_id,
            self.wsi_root / file_id,
        ]
        suffix = image_rel.suffix.lower()

        for file_id_dir in candidate_dirs:
            if not file_id_dir.is_dir():
                continue

            candidates = [p for p in file_id_dir.iterdir() if p.is_file()]
            if suffix:
                candidates = [p for p in candidates if p.suffix.lower() == suffix]

            if len(candidates) == 1:
                return candidates[0]

            if len(candidates) > 1:
                stem = image_rel.stem
                prefix_matches = [
                    p
                    for p in candidates
                    if p.name.startswith(stem) or p.name.startswith(f"{stem}.")
                ]
                if len(prefix_matches) == 1:
                    return prefix_matches[0]

        return None

    def _try_resolve_uuid_suffixed_filename(
        self,
        *,
        image_rel: Path,
        wsi_subdir: str,
    ) -> Path | None:
        """Resolve a uuid-suffixed TCGA filename in a directory.

        Example: TCGA-...-DX1.<uuid>.svs
        """
        if not image_rel.suffix:
            return None

        pattern = f"{image_rel.stem}.*{image_rel.suffix}"
        for candidate_dir in (self.wsi_root / wsi_subdir, self.wsi_root):
            if not candidate_dir.is_dir():
                continue

            matches = sorted(p for p in candidate_dir.glob(pattern) if p.is_file())
            if len(matches) == 1:
                return matches[0]
            if len(matches) > 1:
                raise FileNotFoundError(
                    f"WSI resolution ambiguous for {image_rel.name!r}: "
                    f"found multiple candidates under {candidate_dir}"
                )

        return None

    def _try_resolve_dicom_directory(
        self,
        *,
        image_rel: Path,
        wsi_subdir: str,
    ) -> Path | None:
        """Resolve a DICOM WSI from a directory of .dcm files.

        For GTEx images from IDC, the layout is:
            gtex/GTEX-OIZH-0626/*.dcm

        OpenSlide 4.0.0+ can read DICOM WSI by opening any .dcm file in the
        directory; it scans sibling files with the same Series Instance UID.

        Example: GTEX-OIZH-0626.tiff -> gtex/GTEX-OIZH-0626/<any>.dcm
        """
        # Use stem without extension as directory name
        dicom_dir_name = image_rel.stem

        for candidate_parent in (self.wsi_root / wsi_subdir, self.wsi_root):
            dicom_dir = candidate_parent / dicom_dir_name
            if not dicom_dir.is_dir():
                continue

            # Find any .dcm file in the directory
            dcm_files = sorted(dicom_dir.glob("*.dcm"))
            if dcm_files:
                # Return the first .dcm file; OpenSlide will find siblings
                return dcm_files[0]

        return None

    def resolve(
        self,
        image_path: str,
        benchmark_name: str,
        *,
        file_id: str | None = None,
    ) -> Path:
        """Resolve a WSI path under `wsi_root`.

        Tries:
        1. wsi_root / image_path
        2. wsi_root / <benchmark-subdir> / image_path
        3. (TCGA/GDC) wsi_root / <benchmark-subdir> / file_id / <downloaded filename>
        4. (TCGA/GDC) wsi_root / <benchmark-subdir> / image_stem.*<suffix>
        5. (GTEx/DICOM) wsi_root / <benchmark-subdir> / image_stem / *.dcm

        Raises:
            FileNotFoundError: If WSI file is not found.
            ValueError: If image_path attempts path traversal.
        """
        image_rel = Path(image_path)
        if image_rel.is_absolute() or image_rel.drive:
            raise ValueError(
                f"Invalid image_path {image_path!r}: absolute paths are not allowed."
            )
        if ".." in image_rel.parts:
            raise ValueError(
                f"Invalid image_path {image_path!r}: path traversal is not allowed."
            )

        wsi_subdir = self.wsi_subdir_for_benchmark(benchmark_name)

        # Try direct path
        direct_path = self.wsi_root / image_rel
        if direct_path.exists():
            return direct_path

        # Try benchmark subdirectory
        subdir_path = self.wsi_root / wsi_subdir / image_rel
        if subdir_path.exists():
            return subdir_path

        # Try gdc-client style downloads (wsi_subdir/file_id/<uuid-suffixed filename>)
        if file_id is not None:
            resolved = self._try_resolve_file_id_dir(
                image_rel=image_rel,
                wsi_subdir=wsi_subdir,
                file_id=file_id,
            )
            if resolved is not None:
                return resolved

        resolved = self._try_resolve_uuid_suffixed_filename(
            image_rel=image_rel,
            wsi_subdir=wsi_subdir,
        )
        if resolved is not None:
            return resolved

        # Try DICOM directory (e.g., GTEx from IDC: gtex/GTEX-OIZH-0626/*.dcm)
        resolved = self._try_resolve_dicom_directory(
            image_rel=image_rel,
            wsi_subdir=wsi_subdir,
        )
        if resolved is not None:
            return resolved

        raise FileNotFoundError(
            f"WSI not found: tried {direct_path} and {subdir_path}. "
            "Please ensure the WSI is available under --wsi-root."
        )
