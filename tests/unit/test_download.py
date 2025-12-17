"""Unit tests for dataset download helpers (no network)."""

from __future__ import annotations

from pathlib import Path

import pytest

from giant.data import download as dl


def test_download_multipathqa_metadata_calls_hf_hub_download(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    def fake_hf_hub_download(*, local_dir: Path, **kwargs: object) -> str:
        calls.update(kwargs)
        calls["local_dir"] = local_dir
        fake_csv = Path(local_dir) / dl.MULTIPATHQA_CSV_FILENAME
        fake_csv.write_text("benchmark_name\npanda\n", encoding="utf-8")
        return str(fake_csv)

    monkeypatch.setattr(dl, "hf_hub_download", fake_hf_hub_download)

    out_dir = tmp_path / "data" / "multipathqa"
    csv_path = dl.download_multipathqa_metadata(out_dir)

    assert csv_path.exists()
    assert csv_path.name == dl.MULTIPATHQA_CSV_FILENAME
    assert calls["repo_id"] == dl.MULTIPATHQA_REPO_ID
    assert calls["filename"] == dl.MULTIPATHQA_CSV_FILENAME
    assert Path(calls["local_dir"]) == out_dir


def test_main_logs_download_event(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    csv_path = tmp_path / dl.MULTIPATHQA_CSV_FILENAME
    csv_path.write_text("benchmark_name\npanda\n", encoding="utf-8")

    events: list[tuple[str, dict[str, object]]] = []

    class DummyLogger:
        def info(self, event: str, **kwargs: object) -> None:
            events.append((event, kwargs))

    monkeypatch.setattr(dl, "configure_logging", lambda: None)
    monkeypatch.setattr(dl, "get_logger", lambda _name=None: DummyLogger())
    monkeypatch.setattr(dl, "download_multipathqa_metadata", lambda: csv_path)

    dl.main()

    assert events
    event, kwargs = events[0]
    assert event == "Downloaded MultiPathQA metadata CSV"
    assert kwargs["path"] == str(csv_path)
