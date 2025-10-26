from __future__ import annotations

import json
import logging
from pathlib import Path
from zipfile import ZipFile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.environment import EnvironmentState
from app.models.files import FileMetadata
from app.models.training import TrainingAlgorithm, TrainingJob, TrainingJobStatus
from app.tasks import file_tasks


def _create_log_directory(root: Path) -> Path:
    logs_dir = root / "logs"
    (logs_dir / "nested").mkdir(parents=True)
    (logs_dir / "server.log").write_text("root-log")
    (logs_dir / "nested" / "worker.log").write_text("worker-log")
    return logs_dir


def test_archive_logs_directory(tmp_path: Path) -> None:
    archive_root = tmp_path / "archives"
    archive_root.mkdir(parents=True)
    file_tasks.ARCHIVE_ROOT = archive_root

    logs_dir = _create_log_directory(tmp_path)

    archive_path = Path(file_tasks.archive_logs.run(str(logs_dir)))

    assert archive_path.exists()
    assert archive_path.suffix == ".zip"
    assert archive_path.parent == archive_root / "logs"

    with ZipFile(archive_path) as archive:
        namelist = set(archive.namelist())
        assert "server.log" in namelist
        assert "nested/worker.log" in namelist
        assert archive.read("server.log").decode() == "root-log"


def test_archive_logs_file(tmp_path: Path) -> None:
    archive_root = tmp_path / "archives"
    archive_root.mkdir(parents=True)
    file_tasks.ARCHIVE_ROOT = archive_root

    log_file = tmp_path / "training.log"
    log_file.write_text("log-line")

    archive_path = Path(file_tasks.archive_logs.run(str(log_file)))

    assert archive_path.exists()
    assert archive_path.suffix == ".zip"
    assert archive_path.parent == archive_root / "training"

    with ZipFile(archive_path) as archive:
        assert archive.namelist() == ["training.log"]
        assert archive.read("training.log").decode() == "log-line"


def test_archive_logs_missing_path_raises(tmp_path: Path) -> None:
    archive_root = tmp_path / "archives"
    archive_root.mkdir(parents=True)
    file_tasks.ARCHIVE_ROOT = archive_root

    missing = tmp_path / "missing"

    with pytest.raises(ValueError):
        file_tasks.archive_logs.run(str(missing))


def _configure_in_memory_db(monkeypatch: pytest.MonkeyPatch) -> sessionmaker:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)
    monkeypatch.setattr(file_tasks, "SessionLocal", Session)
    return Session


def _seed_playback_states(session: sessionmaker, job: TrainingJob) -> int:
    with session() as db:
        db.add(job)
        db.commit()
        job_id = job.id
        states = [
            EnvironmentState(
                session_id=job_id,
                episode=0,
                step=0,
                robot_x=1,
                robot_y=2,
                robot_orientation=0,
                threat_grid={"levels": [[0.1, 0.2], [0.3, 0.4]]},
                coverage_map={"counts": [[1, 0], [0, 0]]},
                suspicious_objects=None,
                action_taken=1,
                reward_received=0.5,
            ),
            EnvironmentState(
                session_id=job_id,
                episode=0,
                step=1,
                robot_x=2,
                robot_y=3,
                robot_orientation=1,
                threat_grid={"levels": [[0.2, 0.3], [0.4, 0.5]]},
                coverage_map=None,
                suspicious_objects={"items": ["box"]},
                action_taken=2,
                reward_received=0.8,
            ),
        ]
        db.add_all(states)
        db.commit()
        return job_id


def test_archive_playback_session_registers_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    storage_root = tmp_path / "storage"
    storage_root.mkdir(parents=True)
    monkeypatch.setattr(file_tasks.storage, "STORAGE_ROOT", storage_root)
    playback_root = storage_root / "playback_archives"
    playback_root.mkdir(parents=True)
    monkeypatch.setattr(file_tasks, "PLAYBACK_ARCHIVE_ROOT", playback_root)

    Session = _configure_in_memory_db(monkeypatch)

    redis_stub = object()
    published: dict[str, object] = {}

    def fake_create() -> object:
        return redis_stub

    def fake_publish(client: object, session_id: int, payload: dict[str, object], *, critical: bool, max_retries: int = 3) -> None:
        published["client"] = client
        published["session_id"] = session_id
        published["payload"] = payload
        published["critical"] = critical

    monkeypatch.setattr(file_tasks, "_create_redis_client", fake_create)
    monkeypatch.setattr(file_tasks, "_publish_training_event", fake_publish)

    job = TrainingJob(
        name="demo",
        algorithm=TrainingAlgorithm.ppo,
        environment_type="standard",
        status=TrainingJobStatus.created,
        total_timesteps=10,
    )
    job_id = _seed_playback_states(Session, job)

    result = file_tasks.archive_playback_session.run(job_id)

    archive_path = storage_root / Path(result["file_path"])
    assert archive_path.exists()
    assert result["frame_count"] == 2

    with ZipFile(archive_path) as archive:
        entries = archive.namelist()
        assert entries == ["frames.jsonl"]
        lines = archive.read("frames.jsonl").decode("utf-8").strip().splitlines()
        assert len(lines) == 2
        first_record = json.loads(lines[0])
        assert first_record["episode"] == 0
        assert first_record["step"] == 0

    with Session() as db:
        remaining = (
            db.query(EnvironmentState)
            .filter(EnvironmentState.session_id == job_id)
            .count()
        )
        assert remaining == 0

        files = db.query(FileMetadata).all()
        assert len(files) == 1
        metadata = files[0].metadata_ or {}
        assert metadata.get("session_id") == job_id
        assert metadata.get("frame_count") == 2
        assert isinstance(metadata.get("transaction_id"), str)
        assert metadata.get("transaction_id")
        transaction_id = metadata.get("transaction_id")

    assert published["client"] is redis_stub
    assert published["session_id"] == job_id
    assert published["critical"] is True
    payload = published["payload"]
    assert payload["event"] == "playback_archived"
    assert payload["file_id"] == result["file_id"]
    assert payload["file_path"] == result["file_path"]
    assert payload["frame_count"] == 2
    assert isinstance(payload["transaction_id"], str)
    assert payload["transaction_id"]
    assert payload["transaction_id"] == transaction_id


def test_archive_playback_session_respects_chunk_size_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    storage_root = tmp_path / "storage"
    storage_root.mkdir(parents=True)
    monkeypatch.setattr(file_tasks.storage, "STORAGE_ROOT", storage_root)
    playback_root = storage_root / "playback_archives"
    playback_root.mkdir(parents=True)
    monkeypatch.setattr(file_tasks, "PLAYBACK_ARCHIVE_ROOT", playback_root)

    Session = _configure_in_memory_db(monkeypatch)

    monkeypatch.setattr(file_tasks, "_create_redis_client", lambda: object())
    monkeypatch.setattr(
        file_tasks,
        "_publish_training_event",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(file_tasks.settings, "playback_archive_chunk_size", 1)

    job = TrainingJob(
        name="chunk-size",
        algorithm=TrainingAlgorithm.ppo,
        environment_type="standard",
        status=TrainingJobStatus.created,
        total_timesteps=10,
    )
    job_id = _seed_playback_states(Session, job)

    caplog.set_level(logging.DEBUG, logger=file_tasks.logger.name)

    file_tasks.archive_playback_session.run(job_id)

    debug_exports = [
        record
        for record in caplog.records
        if record.levelno == logging.DEBUG and "Exported" in record.getMessage()
    ]
    assert len(debug_exports) == 2


def test_archive_playback_session_enforces_archive_size_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage_root = tmp_path / "storage"
    storage_root.mkdir(parents=True)
    monkeypatch.setattr(file_tasks.storage, "STORAGE_ROOT", storage_root)
    playback_root = storage_root / "playback_archives"
    playback_root.mkdir(parents=True)
    monkeypatch.setattr(file_tasks, "PLAYBACK_ARCHIVE_ROOT", playback_root)

    Session = _configure_in_memory_db(monkeypatch)

    monkeypatch.setattr(file_tasks, "_create_redis_client", lambda: object())
    monkeypatch.setattr(
        file_tasks,
        "_publish_training_event",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(file_tasks.settings, "playback_archive_max_bytes", 1)

    job = TrainingJob(
        name="oversize",
        algorithm=TrainingAlgorithm.ppo,
        environment_type="standard",
        status=TrainingJobStatus.created,
        total_timesteps=10,
    )
    job_id = _seed_playback_states(Session, job)

    with pytest.raises(ValueError) as excinfo:
        file_tasks.archive_playback_session.run(job_id)

    assert "exceeds maximum size" in str(excinfo.value)
    assert not list(playback_root.rglob("*.zip"))


def test_archive_playback_session_without_frames_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    storage_root = tmp_path / "storage"
    storage_root.mkdir(parents=True)
    monkeypatch.setattr(file_tasks.storage, "STORAGE_ROOT", storage_root)
    playback_root = storage_root / "playback_archives"
    playback_root.mkdir(parents=True)
    monkeypatch.setattr(file_tasks, "PLAYBACK_ARCHIVE_ROOT", playback_root)

    Session = _configure_in_memory_db(monkeypatch)

    job = TrainingJob(
        name="empty",
        algorithm=TrainingAlgorithm.ppo,
        environment_type="standard",
        status=TrainingJobStatus.created,
        total_timesteps=5,
    )
    with Session() as db:
        db.add(job)
        db.commit()
        job_id = job.id

    with pytest.raises(ValueError):
        file_tasks.archive_playback_session.run(job_id)

    assert not any(playback_root.iterdir())


def test_archive_playback_session_validates_session_id(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummySession:
        def rollback(self) -> None:
            pass

        def close(self) -> None:
            pass

    monkeypatch.setattr(file_tasks, "SessionLocal", lambda: DummySession())

    with pytest.raises(ValueError):
        file_tasks.archive_playback_session.run(0)

    with pytest.raises(ValueError):
        file_tasks.archive_playback_session.run(-1)

    with pytest.raises(ValueError):
        file_tasks.archive_playback_session.run("abc")  # type: ignore[arg-type]
