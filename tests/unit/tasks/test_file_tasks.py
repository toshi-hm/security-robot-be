from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

import pytest

from app.tasks.file_tasks import archive_logs


def _create_log_directory(root: Path) -> Path:
    logs_dir = root / "logs"
    (logs_dir / "nested").mkdir(parents=True)
    (logs_dir / "server.log").write_text("root-log")
    (logs_dir / "nested" / "worker.log").write_text("worker-log")
    return logs_dir


def test_archive_logs_directory(tmp_path: Path) -> None:
    logs_dir = _create_log_directory(tmp_path)

    archive_path = Path(archive_logs.run(str(logs_dir)))

    assert archive_path.exists()
    assert archive_path.suffix == ".zip"

    with ZipFile(archive_path) as archive:
        namelist = set(archive.namelist())
        assert "server.log" in namelist
        assert "nested/worker.log" in namelist
        assert archive.read("server.log").decode() == "root-log"


def test_archive_logs_file(tmp_path: Path) -> None:
    log_file = tmp_path / "training.log"
    log_file.write_text("log-line")

    archive_path = Path(archive_logs.run(str(log_file)))

    assert archive_path.exists()
    assert archive_path.suffix == ".zip"

    with ZipFile(archive_path) as archive:
        assert archive.namelist() == ["training.log"]
        assert archive.read("training.log").decode() == "log-line"


def test_archive_logs_missing_path_raises(tmp_path: Path) -> None:
    missing = tmp_path / "missing"

    with pytest.raises(ValueError):
        archive_logs.run(str(missing))
