"""Tests for the job queue inspection API endpoints."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.api.v1.endpoints import jobs as jobs_module
from app.core.training import job_manager as job_manager_module
from app.core.training.job_manager import JobManager
from fastapi import HTTPException
from tests.utils.time import set_time_sequence


@pytest.fixture
def job_manager_stub(monkeypatch: pytest.MonkeyPatch) -> JobManager:
    """Provide a fresh job manager instance for each test."""

    manager = JobManager()
    monkeypatch.setattr(jobs_module, "job_manager", manager)
    return manager


@pytest.mark.asyncio
async def test_list_jobs_returns_queue_entries(
    job_manager_stub: JobManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = datetime(2025, 10, 21, 12, 0, tzinfo=UTC)
    set_time_sequence(monkeypatch, job_manager_module, base, base + timedelta(minutes=1))

    await job_manager_stub.enqueue({"session_id": 10, "task_id": "task-10"})
    await job_manager_stub.enqueue({"session_id": 11, "task_id": "task-11"})

    response = await jobs_module.list_jobs()

    assert len(response.jobs) == 2
    first, second = response.jobs
    assert first.session_id == 10
    assert first.task_id == "task-10"
    assert first.status == "queued"
    assert second.session_id == 11
    assert second.task_id == "task-11"


@pytest.mark.asyncio
async def test_get_job_returns_detail(job_manager_stub: JobManager) -> None:
    await job_manager_stub.enqueue({"session_id": 21, "task_id": "task-21"})

    response = await jobs_module.get_job(21)

    assert response.job.session_id == 21
    assert response.job.task_id == "task-21"


@pytest.mark.asyncio
async def test_get_job_missing_raises(job_manager_stub: JobManager) -> None:
    with pytest.raises(HTTPException) as excinfo:
        await jobs_module.get_job(99)

    assert excinfo.value.status_code == 404
    assert "not found" in excinfo.value.detail.lower()


@pytest.mark.asyncio
async def test_delete_job_removes_entry(job_manager_stub: JobManager) -> None:
    await job_manager_stub.enqueue({"session_id": 33, "task_id": "task-33"})

    await jobs_module.delete_job(33)

    assert job_manager_stub.get(33) is None
