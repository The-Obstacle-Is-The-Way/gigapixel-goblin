"""TCGA (GDC) helpers for MultiPathQA WSI acquisition.

This module focuses on the *open-access* TCGA slide images used by MultiPathQA.
It supports:
- Estimating total download size via the public GDC API
- Downloading a small subset (e.g., the smallest slides) for E2E smoke testing

It intentionally does not attempt to solve GTEx/PANDA acquisition, which involve
different distribution channels and terms.
"""

from __future__ import annotations

import argparse
import csv
import shutil
from dataclasses import dataclass
from pathlib import Path

import httpx

from giant.utils.logging import configure_logging, get_logger

GDC_BASE_URL = "https://api.gdc.cancer.gov"

_TCGA_BENCHMARKS = {"tcga", "tcga_expert_vqa", "tcga_slidebench"}


@dataclass(frozen=True)
class GdcFile:
    file_id: str
    file_name: str
    file_size: int


def _read_multipathqa_tcga_mapping(csv_path: Path) -> dict[str, str]:
    """Return a mapping of GDC file_id -> MultiPathQA image_path for TCGA slides."""
    mapping: dict[str, str] = {}
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("benchmark_name") not in _TCGA_BENCHMARKS:
                continue

            file_id = (row.get("file_id") or "").strip()
            image_path = (row.get("image_path") or "").strip()
            if not file_id or not image_path:
                raise ValueError("MultiPathQA TCGA row missing file_id or image_path")

            existing = mapping.get(file_id)
            if existing is not None and existing != image_path:
                raise ValueError(
                    f"Conflicting image_path for file_id {file_id!r}: "
                    f"{existing!r} vs {image_path!r}"
                )
            mapping[file_id] = image_path

    if not mapping:
        raise ValueError("No TCGA rows found in MultiPathQA.csv")
    return mapping


def _fetch_gdc_metadata(file_ids: list[str]) -> list[GdcFile]:
    """Fetch GDC metadata (name/size) for a list of file_ids."""
    payload = {
        "filters": {
            "op": "in",
            "content": {"field": "file_id", "value": file_ids},
        },
        "fields": "file_id,file_name,file_size,access,data_format,data_type",
        "format": "JSON",
        "size": len(file_ids),
    }

    with httpx.Client(timeout=60.0) as client:
        resp = client.post(f"{GDC_BASE_URL}/files", json=payload)
        resp.raise_for_status()
        hits = resp.json()["data"]["hits"]

    files: list[GdcFile] = []
    for hit in hits:
        files.append(
            GdcFile(
                file_id=str(hit["file_id"]),
                file_name=str(hit["file_name"]),
                file_size=int(hit["file_size"]),
            )
        )
    return files


def _format_bytes(n_bytes: int) -> str:
    gib = n_bytes / 1024**3
    if gib >= 1:
        return f"{gib:.2f} GiB"
    mib = n_bytes / 1024**2
    return f"{mib:.1f} MiB"


def estimate_tcga_size(csv_path: Path) -> tuple[int, list[GdcFile]]:
    """Return (total_bytes, per-file metadata) for TCGA slides in MultiPathQA."""
    mapping = _read_multipathqa_tcga_mapping(csv_path)
    files = _fetch_gdc_metadata(sorted(mapping.keys()))
    total_bytes = sum(f.file_size for f in files)
    return total_bytes, files


def _download_gdc_file(
    *,
    file: GdcFile,
    out_dir: Path,
    reserve_bytes: int,
) -> Path:
    """Download a single file into gdc-client style layout.

    Layout: out_dir/<file_id>/<file_name>
    """
    # Validate file_id safety
    fid = Path(file.file_id)
    if fid.is_absolute() or fid.drive or ".." in fid.parts or fid.name != file.file_id:
        raise ValueError(f"Invalid file_id {file.file_id!r}")

    # Validate file_name safety
    fname = Path(file.file_name)
    if (
        fname.is_absolute()
        or fname.drive
        or ".." in fname.parts
        or fname.name != file.file_name
    ):
        raise ValueError(f"Invalid file_name {file.file_name!r}")

    dest_dir = out_dir / file.file_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / file.file_name

    if dest_path.exists() and dest_path.stat().st_size == file.file_size:
        return dest_path

    free_bytes = shutil.disk_usage(dest_dir).free
    if free_bytes < file.file_size + reserve_bytes:
        raise RuntimeError(
            f"Not enough free space to download {file.file_id} "
            f"({_format_bytes(file.file_size)}). "
            f"Free: {_format_bytes(free_bytes)}; "
            f"reserve: {_format_bytes(reserve_bytes)}."
        )

    tmp_path = dest_dir / f"{file.file_name}.part"
    if tmp_path.exists():
        tmp_path.unlink()

    url = f"{GDC_BASE_URL}/data/{file.file_id}"
    timeout = httpx.Timeout(60.0, read=None)
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        with client.stream("GET", url) as resp:
            resp.raise_for_status()
            with tmp_path.open("wb") as f:
                for chunk in resp.iter_bytes(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)

    if tmp_path.stat().st_size != file.file_size:
        tmp_size = tmp_path.stat().st_size
        tmp_path.unlink(missing_ok=True)
        raise RuntimeError(
            f"Downloaded size mismatch for {file.file_id}: "
            f"expected {file.file_size}, got {tmp_size}"
        )

    tmp_path.replace(dest_path)
    return dest_path


def main() -> None:
    configure_logging()
    logger = get_logger(__name__)

    parser = argparse.ArgumentParser(
        prog="python -m giant.data.tcga",
        description="TCGA (GDC) helpers for MultiPathQA slide acquisition.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    est = sub.add_parser("estimate", help="Estimate total TCGA download size.")
    est.add_argument(
        "--csv-path",
        type=Path,
        default=Path("data/multipathqa/MultiPathQA.csv"),
    )
    est.add_argument("--top", type=int, default=10)

    dl = sub.add_parser("download", help="Download a TCGA subset via the GDC API.")
    dl.add_argument(
        "--csv-path",
        type=Path,
        default=Path("data/multipathqa/MultiPathQA.csv"),
    )
    dl.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data/wsi/tcga"),
        help="Directory to download into (gdc-client style layout).",
    )
    dl.add_argument(
        "--smallest",
        type=int,
        default=0,
        help="Download the N smallest slides (by GDC file_size).",
    )
    dl.add_argument(
        "--reserve-gib",
        type=float,
        default=2.0,
        help="Keep at least this much free space on the filesystem.",
    )
    dl.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()

    total_bytes, files = estimate_tcga_size(args.csv_path)
    logger.info(
        "TCGA slides referenced by MultiPathQA",
        n_files=len(files),
        total=_format_bytes(total_bytes),
    )

    files_sorted = sorted(files, key=lambda f: f.file_size)

    if args.command == "estimate":
        top_n = max(0, int(args.top))
        smallest = files_sorted[:top_n]
        largest = list(reversed(files_sorted[-top_n:]))

        print(f"Total TCGA slides: {len(files_sorted)}")
        print(f"Total size: {_format_bytes(total_bytes)}")
        if top_n:
            print("\nSmallest:")
            for f in smallest:
                print(f"  {_format_bytes(f.file_size):>10}  {f.file_id}  {f.file_name}")
            print("\nLargest:")
            for f in largest:
                print(f"  {_format_bytes(f.file_size):>10}  {f.file_id}  {f.file_name}")
        return

    if args.smallest <= 0:
        raise SystemExit("--smallest must be >= 1 for the download command")

    reserve_bytes = int(float(args.reserve_gib) * 1024**3)
    to_download = files_sorted[: int(args.smallest)]
    planned_bytes = sum(f.file_size for f in to_download)

    print(
        f"Planned downloads: {len(to_download)} files ({_format_bytes(planned_bytes)})"
    )
    for f in to_download:
        print(f"  {_format_bytes(f.file_size):>10}  {f.file_id}  {f.file_name}")

    if args.dry_run:
        return

    for f in to_download:
        path = _download_gdc_file(
            file=f,
            out_dir=args.out_dir,
            reserve_bytes=reserve_bytes,
        )
        logger.info("Downloaded", file_id=f.file_id, path=str(path))


if __name__ == "__main__":  # pragma: no cover
    main()
