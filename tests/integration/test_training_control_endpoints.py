from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.deps import get_db
from app.api.v1.endpoints import jobs as jobs_module
from app.api.v1.endpoints import training as training_module
from app.core.training.job_manager import JobManager
from app.db import database as database_module
from app.db import session as session_module
import app.main as main_module
from app.main import create_app
from app.models.training import TrainingJob, TrainingJobStatus
from fastapi import FastAPI


class _DispatcherStub:
    def __init__(self) -> None:
        self.dispatched: list[dict[str, object]] = []
        self.stopped: list[int] = []
        self.revoked: list[dict[str, object]] = []

    def dispatch(self, job: TrainingJob, config: dict) -> SimpleNamespace:
        task_id = f"task-{job.id}-{len(self.dispatched) + 1}"
        self.dispatched.append(
            {
                "session_id": job.id,
                "algorithm": job.algorithm,
                "config": config,
                "task_id": task_id,
            }
        )
        return SimpleNamespace(id=task_id)

    def stop(self, session_id: int) -> SimpleNamespace:
        self.stopped.append(session_id)
        return SimpleNamespace(id=f"stop-{session_id}")

    def revoke(
        self,
        task_id: str,
        *,
        terminate: bool = True,
        signal: str | None = "SIGTERM",
    ) -> SimpleNamespace:
        self.revoked.append(
            {
                "task_id": task_id,
                "terminate": terminate,
                "signal": signal,
            }
        )
        return SimpleNamespace(id=task_id)


def _assert_recent(timestamp: datetime, *, window_seconds: int = 5) -> None:
    """Assert that a timestamp is within ``window_seconds`` of now."""

    delta = abs((datetime.now(UTC) - timestamp).total_seconds())
    assert delta < window_seconds, (
        f"Expected {timestamp!r} to be within {window_seconds}s of now (delta={delta:.4f})"
    )


@pytest.fixture()
def training_api_app(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[FastAPI, async_sessionmaker[AsyncSession], JobManager, _DispatcherStub]:
    """Provide a FastAPI app wired to an in-memory database and fresh job manager."""

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    monkeypatch.setattr(database_module, "database_engine", engine)
    monkeypatch.setattr(main_module, "database_engine", engine)
    monkeypatch.setattr(session_module, "async_session", session_maker)

    job_manager = JobManager()
    monkeypatch.setattr(training_module, "job_manager", job_manager)
    monkeypatch.setattr(jobs_module, "job_manager", job_manager)

    dispatcher_stub = _DispatcherStub()
    monkeypatch.setattr(training_module, "training_dispatcher", dispatcher_stub)

    app = create_app()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    yield app, session_maker, job_manager, dispatcher_stub

    app.dependency_overrides.clear()
    asyncio.run(engine.dispose())


def _load_job(session_maker: async_sessionmaker[AsyncSession], job_id: int) -> TrainingJob | None:
    async def _get() -> TrainingJob | None:
        async with session_maker() as session:
            return await session.get(TrainingJob, job_id)

    return asyncio.run(_get())


def test_start_training_creates_session_and_enqueues_job(
    training_api_app: tuple[FastAPI, async_sessionmaker[AsyncSession], JobManager, _DispatcherStub],
) -> None:
    app, session_maker, job_manager, dispatcher = training_api_app

    payload = {
        "name": "Integration job",
        "algorithm": "ppo",
        "environment_type": "standard",
        "total_timesteps": 500,
        "env_width": 8,
        "env_height": 8,
        "coverage_weight": 1.5,
        "exploration_weight": 3.0,
        "diversity_weight": 2.0,
        "learning_rate": 0.0003,
        "batch_size": 64,
        "num_workers": 1,
        "config": {"seed": 123},
    }

    with TestClient(app) as client:
        response = client.post("/api/v1/training/start", json=payload)

    assert response.status_code == 202
    body = response.json()
    assert body["name"] == payload["name"]
    assert body["status"] == TrainingJobStatus.queued.value

    job = _load_job(session_maker, body["id"])
    assert job is not None
    assert job.status is TrainingJobStatus.queued

    queue_entries = job_manager.snapshot()
    assert len(queue_entries) == 1
    entry = queue_entries[0]
    assert entry["session_id"] == body["id"]
    assert entry["task_id"] == dispatcher.dispatched[0]["task_id"]

    assert dispatcher.dispatched[0]["config"]["total_timesteps"] == payload["total_timesteps"]


def test_pause_unknown_session_returns_not_found(
    training_api_app: tuple[FastAPI, async_sessionmaker[AsyncSession], JobManager, _DispatcherStub],
) -> None:
    app, _, _, _ = training_api_app

    with TestClient(app) as client:
        response = client.post("/api/v1/training/999/pause")

    assert response.status_code == 404
    payload = response.json()
    assert payload["detail"].startswith("Training session 999 not found")


def test_resume_requires_paused_status(
    training_api_app: tuple[FastAPI, async_sessionmaker[AsyncSession], JobManager, _DispatcherStub],
) -> None:
    app, _, _, _ = training_api_app

    payload = {
        "name": "Queued job",
        "algorithm": "ppo",
        "environment_type": "standard",
        "total_timesteps": 200,
        "env_width": 6,
        "env_height": 6,
        "coverage_weight": 1.0,
        "exploration_weight": 2.5,
        "diversity_weight": 1.5,
        "learning_rate": 0.0005,
        "batch_size": 32,
        "num_workers": 1,
        "config": None,
    }

    with TestClient(app) as client:
        start_response = client.post("/api/v1/training/start", json=payload)
        assert start_response.status_code == 202
        session_id = start_response.json()["id"]

        resume_response = client.post(f"/api/v1/training/{session_id}/resume")

    assert resume_response.status_code == 400
    error = resume_response.json()
    assert "paused" in error["detail"].lower()


def test_resume_requeues_paused_session_dispatches_job(
    training_api_app: tuple[FastAPI, async_sessionmaker[AsyncSession], JobManager, _DispatcherStub],
) -> None:
    app, session_maker, job_manager, dispatcher = training_api_app

    payload = {
        "name": "Paused job",
        "algorithm": "ppo",
        "environment_type": "standard",
        "total_timesteps": 200,
        "env_width": 6,
        "env_height": 6,
        "coverage_weight": 1.0,
        "exploration_weight": 2.5,
        "diversity_weight": 1.5,
        "learning_rate": 0.0005,
        "batch_size": 32,
        "num_workers": 1,
        "config": None,
    }

    with TestClient(app) as client:
        start_response = client.post("/api/v1/training/start", json=payload)
        assert start_response.status_code == 202
        session_id = start_response.json()["id"]

    async def _mark_paused() -> None:
        async with session_maker() as session:
            job = await session.get(TrainingJob, session_id)
            assert job is not None
            job.status = TrainingJobStatus.paused
            await session.commit()

    asyncio.run(_mark_paused())
    asyncio.run(job_manager.stop(session_id, reason="paused"))

    with TestClient(app) as client:
        resume_response = client.post(f"/api/v1/training/{session_id}/resume")

    assert resume_response.status_code == 200
    body = resume_response.json()
    assert body["status"] == TrainingJobStatus.queued.value

    job = _load_job(session_maker, session_id)
    assert job is not None
    assert job.status is TrainingJobStatus.queued

    queue_entries = job_manager.snapshot()
    assert len(queue_entries) == 1
    entry = queue_entries[0]
    assert entry["status"] == "queued"
    assert entry["task_id"] == dispatcher.dispatched[-1]["task_id"]

    assert len(dispatcher.dispatched) == 2
    resume_config = dispatcher.dispatched[-1]["config"]
    assert resume_config["session_id"] == session_id
    assert resume_config["total_timesteps"] == payload["total_timesteps"]


def test_stop_training_marks_job_failed_and_stops_queue_entry(
    training_api_app: tuple[FastAPI, async_sessionmaker[AsyncSession], JobManager, _DispatcherStub],
) -> None:
    app, session_maker, job_manager, dispatcher = training_api_app

    payload = {
        "name": "Stopping job",
        "algorithm": "ppo",
        "environment_type": "standard",
        "total_timesteps": 100,
        "env_width": 5,
        "env_height": 5,
        "coverage_weight": 1.0,
        "exploration_weight": 2.0,
        "diversity_weight": 1.0,
        "learning_rate": 0.0003,
        "batch_size": 16,
        "num_workers": 1,
        "config": None,
    }

    with TestClient(app) as client:
        start_response = client.post("/api/v1/training/start", json=payload)
        assert start_response.status_code == 202
        session_id = start_response.json()["id"]

        stop_response = client.post(f"/api/v1/training/{session_id}/stop")

    assert stop_response.status_code == 200
    body = stop_response.json()
    assert body["status"] == TrainingJobStatus.failed.value
    assert "stopped successfully" in body["message"].lower()
    assert body["celery_task_id"] == f"stop-{session_id}"
    assert body["queue_task_id"] == dispatcher.dispatched[0]["task_id"]
    assert body["revoked_task_id"] is None
    assert body["forced"] is False
    assert body["paused_at"] is None
    assert body["revoked_at"] is None
    assert body["resumed_at"] is None
    stopped_at = datetime.fromisoformat(body["stopped_at"])
    _assert_recent(stopped_at)

    job = _load_job(session_maker, session_id)
    assert job is not None
    assert job.status is TrainingJobStatus.failed
    assert job.completed_at is not None

    queue_entries = job_manager.snapshot()
    assert len(queue_entries) == 1
    queue_entry = queue_entries[0]
    assert queue_entry["status"] == "stopped"
    assert queue_entry["forced"] is False
    assert queue_entry["stopped_at"] == stopped_at

    assert dispatcher.stopped == [session_id]
    assert dispatcher.revoked == []


def test_force_stop_training_revokes_celery_task(
    training_api_app: tuple[FastAPI, async_sessionmaker[AsyncSession], JobManager, _DispatcherStub],
) -> None:
    app, session_maker, job_manager, dispatcher = training_api_app

    payload = {
        "name": "Force stop job",
        "algorithm": "ppo",
        "environment_type": "standard",
        "total_timesteps": 180,
        "env_width": 6,
        "env_height": 6,
        "coverage_weight": 1.2,
        "exploration_weight": 2.4,
        "diversity_weight": 1.6,
        "learning_rate": 0.0004,
        "batch_size": 32,
        "num_workers": 1,
        "config": None,
    }

    with TestClient(app) as client:
        start_response = client.post("/api/v1/training/start", json=payload)
        assert start_response.status_code == 202
        session_id = start_response.json()["id"]

        stop_response = client.post(
            f"/api/v1/training/{session_id}/stop",
            params={"force": "true"},
        )

    assert stop_response.status_code == 200
    body = stop_response.json()
    assert body["status"] == TrainingJobStatus.failed.value
    assert body["forced"] is True
    assert body["revoked_task_id"] == dispatcher.dispatched[0]["task_id"]
    assert "forcefully" in body["message"].lower()
    assert body["stopped_at"] is None
    assert body["paused_at"] is None
    revoked_at = datetime.fromisoformat(body["revoked_at"])
    _assert_recent(revoked_at)

    job = _load_job(session_maker, session_id)
    assert job is not None
    assert job.status is TrainingJobStatus.failed

    queue_entries = job_manager.snapshot()
    assert len(queue_entries) == 1
    queue_entry = queue_entries[0]
    assert queue_entry["status"] == "revoked"
    assert queue_entry["forced"] is True
    assert queue_entry["revoked_at"] == revoked_at

    assert dispatcher.stopped[-1] == session_id
    assert dispatcher.revoked[-1]["task_id"] == dispatcher.dispatched[0]["task_id"]
    assert dispatcher.revoked[-1]["terminate"] is True


def test_pause_training_updates_queue_entry_and_response_task_ids(
    training_api_app: tuple[FastAPI, async_sessionmaker[AsyncSession], JobManager, _DispatcherStub],
) -> None:
    app, _, job_manager, dispatcher = training_api_app

    payload = {
        "name": "Pausing job",
        "algorithm": "ppo",
        "environment_type": "standard",
        "total_timesteps": 120,
        "env_width": 6,
        "env_height": 6,
        "coverage_weight": 1.1,
        "exploration_weight": 2.1,
        "diversity_weight": 1.3,
        "learning_rate": 0.0003,
        "batch_size": 32,
        "num_workers": 1,
        "config": None,
    }

    with TestClient(app) as client:
        start_response = client.post("/api/v1/training/start", json=payload)
        assert start_response.status_code == 202
        session_id = start_response.json()["id"]

        pause_response = client.post(f"/api/v1/training/{session_id}/pause")

    assert pause_response.status_code == 200
    body = pause_response.json()
    assert body["status"] == TrainingJobStatus.paused.value
    assert body["celery_task_id"] is None
    queue_task_id = body["queue_task_id"]
    assert body["forced"] is False
    assert body["stopped_at"] is None
    assert body["revoked_at"] is None
    paused_at = datetime.fromisoformat(body["paused_at"])
    _assert_recent(paused_at)
    assert body["resumed_at"] is None

    entry = job_manager.get(session_id)
    assert entry is not None
    assert entry["status"] == "paused"
    assert entry["task_id"] == queue_task_id == dispatcher.dispatched[0]["task_id"]
    assert entry["paused_at"] == paused_at


def test_stop_response_includes_resumed_timestamp(
    training_api_app: tuple[FastAPI, async_sessionmaker[AsyncSession], JobManager, _DispatcherStub],
) -> None:
    app, session_maker, job_manager, dispatcher = training_api_app

    payload = {
        "name": "Resume metadata job",
        "algorithm": "ppo",
        "environment_type": "standard",
        "total_timesteps": 200,
        "env_width": 6,
        "env_height": 6,
        "coverage_weight": 1.1,
        "exploration_weight": 2.1,
        "diversity_weight": 1.3,
        "learning_rate": 0.0003,
        "batch_size": 32,
        "num_workers": 1,
        "config": None,
    }

    with TestClient(app) as client:
        start_response = client.post("/api/v1/training/start", json=payload)
        assert start_response.status_code == 202
        session_id = start_response.json()["id"]

        pause_response = client.post(f"/api/v1/training/{session_id}/pause")
        assert pause_response.status_code == 200

        resume_response = client.post(f"/api/v1/training/{session_id}/resume")
        assert resume_response.status_code == 200

        stop_response = client.post(f"/api/v1/training/{session_id}/stop")

    assert stop_response.status_code == 200
    body = stop_response.json()
    assert body["status"] == TrainingJobStatus.failed.value
    assert body["forced"] is False
    assert body["paused_at"] is None
    assert body["revoked_at"] is None
    stopped_at = datetime.fromisoformat(body["stopped_at"])
    resumed_at = datetime.fromisoformat(body["resumed_at"])
    _assert_recent(stopped_at)
    _assert_recent(resumed_at)

    queue_entries = job_manager.snapshot()
    assert len(queue_entries) == 1
    queue_entry = queue_entries[0]
    assert queue_entry["status"] == "stopped"
    assert queue_entry["forced"] is False
    assert queue_entry["stopped_at"] == stopped_at
    assert queue_entry["resumed_at"] == resumed_at

    job = _load_job(session_maker, session_id)
    assert job is not None
    assert job.status is TrainingJobStatus.failed

    assert dispatcher.stopped[-1] == session_id


def test_status_endpoint_returns_persisted_job_state(
    training_api_app: tuple[FastAPI, async_sessionmaker[AsyncSession], JobManager, _DispatcherStub],
) -> None:
    app, _, _, _ = training_api_app

    payload = {
        "name": "Status job",
        "algorithm": "ppo",
        "environment_type": "standard",
        "total_timesteps": 150,
        "env_width": 6,
        "env_height": 6,
        "coverage_weight": 1.2,
        "exploration_weight": 2.2,
        "diversity_weight": 1.4,
        "learning_rate": 0.0004,
        "batch_size": 32,
        "num_workers": 1,
        "config": None,
    }

    with TestClient(app) as client:
        start_response = client.post("/api/v1/training/start", json=payload)
        assert start_response.status_code == 202
        session_id = start_response.json()["id"]

        status_response = client.get(f"/api/v1/training/{session_id}/status")

    assert status_response.status_code == 200
    body = status_response.json()
    assert body["id"] == session_id
    assert body["status"] == TrainingJobStatus.queued.value
    assert body["name"] == payload["name"]


def test_list_training_sessions_returns_latest_first(
    training_api_app: tuple[FastAPI, async_sessionmaker[AsyncSession], JobManager, _DispatcherStub],
) -> None:
    app, _, _, _ = training_api_app

    payload = {
        "algorithm": "ppo",
        "environment_type": "standard",
        "total_timesteps": 120,
        "env_width": 6,
        "env_height": 6,
        "coverage_weight": 1.1,
        "exploration_weight": 2.1,
        "diversity_weight": 1.3,
        "learning_rate": 0.0003,
        "batch_size": 32,
        "num_workers": 1,
        "config": None,
    }

    with TestClient(app) as client:
        for idx in range(1, 4):
            start_payload = {"name": f"Job {idx}", **payload}
            response = client.post("/api/v1/training/start", json=start_payload)
            assert response.status_code == 202

        list_response = client.get("/api/v1/training/list", params={"page": 1, "page_size": 2})

    assert list_response.status_code == 200
    body = list_response.json()
    assert body["total"] == 3
    assert body["page_size"] == 2
    sessions = body["sessions"]
    assert len(sessions) == 2
    assert sessions[0]["name"] == "Job 3"
    assert sessions[1]["name"] == "Job 2"


def test_delete_training_session_removes_job_and_queue_entry(
    training_api_app: tuple[FastAPI, async_sessionmaker[AsyncSession], JobManager, _DispatcherStub],
) -> None:
    app, session_maker, job_manager, _dispatcher = training_api_app

    payload = {
        "name": "Disposable job",
        "algorithm": "ppo",
        "environment_type": "standard",
        "total_timesteps": 80,
        "env_width": 5,
        "env_height": 5,
        "coverage_weight": 1.0,
        "exploration_weight": 2.0,
        "diversity_weight": 1.0,
        "learning_rate": 0.0003,
        "batch_size": 16,
        "num_workers": 1,
        "config": None,
    }

    with TestClient(app) as client:
        start_response = client.post("/api/v1/training/start", json=payload)
        assert start_response.status_code == 202
        session_id = start_response.json()["id"]

        delete_response = client.delete(f"/api/v1/training/{session_id}")

    assert delete_response.status_code == 204
    assert _load_job(session_maker, session_id) is None
    assert job_manager.snapshot() == []


def test_jobs_endpoints_expose_queue_metadata(
    training_api_app: tuple[FastAPI, async_sessionmaker[AsyncSession], JobManager, _DispatcherStub],
) -> None:
    app, _, job_manager, dispatcher = training_api_app

    payload = {
        "name": "Queue job",
        "algorithm": "ppo",
        "environment_type": "standard",
        "total_timesteps": 90,
        "env_width": 5,
        "env_height": 5,
        "coverage_weight": 1.0,
        "exploration_weight": 2.0,
        "diversity_weight": 1.0,
        "learning_rate": 0.0003,
        "batch_size": 16,
        "num_workers": 1,
        "config": None,
    }

    with TestClient(app) as client:
        start_response = client.post("/api/v1/training/start", json=payload)
        assert start_response.status_code == 202
        session_id = start_response.json()["id"]

        list_response = client.get("/api/v1/jobs/")
        detail_response = client.get(f"/api/v1/jobs/{session_id}")
        missing_response = client.get("/api/v1/jobs/9999")

    assert list_response.status_code == 200
    jobs_payload = list_response.json()
    assert isinstance(jobs_payload["jobs"], list)
    assert len(jobs_payload["jobs"]) == 1
    queue_entry = jobs_payload["jobs"][0]
    assert queue_entry["session_id"] == session_id
    assert queue_entry["status"] == "queued"
    assert queue_entry["forced"] is False
    assert queue_entry["payload"]["config"]["name"] == payload["name"]
    assert queue_entry["task_id"] == dispatcher.dispatched[0]["task_id"]
    assert "enqueued_at" in queue_entry

    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    job_entry = detail_payload["job"]
    assert job_entry["session_id"] == session_id
    assert job_entry["task_id"] == dispatcher.dispatched[0]["task_id"]
    assert job_entry["payload"]["config"]["total_timesteps"] == payload["total_timesteps"]
    assert job_entry["enqueued_at"] == queue_entry["enqueued_at"]

    assert missing_response.status_code == 404


def test_jobs_endpoint_allows_removing_queue_entries(
    training_api_app: tuple[FastAPI, async_sessionmaker[AsyncSession], JobManager, _DispatcherStub],
) -> None:
    app, _, job_manager, _dispatcher = training_api_app

    payload = {
        "name": "Queue job",  # reused payload is acceptable
        "algorithm": "ppo",
        "environment_type": "standard",
        "total_timesteps": 90,
        "env_width": 5,
        "env_height": 5,
        "coverage_weight": 1.0,
        "exploration_weight": 2.0,
        "diversity_weight": 1.0,
        "learning_rate": 0.0003,
        "batch_size": 16,
        "num_workers": 1,
        "config": None,
    }

    with TestClient(app) as client:
        start_response = client.post("/api/v1/training/start", json=payload)
        assert start_response.status_code == 202
        session_id = start_response.json()["id"]

        delete_response = client.delete(f"/api/v1/jobs/{session_id}")
        missing_response = client.delete("/api/v1/jobs/9999")

    assert delete_response.status_code == 204
    assert job_manager.get(session_id) is None
    assert missing_response.status_code == 404
