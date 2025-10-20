"""Unit tests for the in-memory job queue manager."""

from __future__ import annotations

from collections import deque
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from app.core.training import job_manager as job_manager_module
from app.core.training.job_manager import JobManager


def _set_time_sequence(monkeypatch: pytest.MonkeyPatch, *timestamps: datetime) -> None:
    """Override ``utcnow`` so successive calls return predictable values."""

    values = deque(timestamps)

    def _utcnow() -> datetime:
        if not values:
            raise AssertionError("utcnow called more times than expected")
        if len(values) == 1:
            return values[0]
        return values.popleft()

    monkeypatch.setattr(job_manager_module, "utcnow", _utcnow)


def _freeze_uuid(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    """Return a deterministic UUID string for queue entries."""

    monkeypatch.setattr(job_manager_module, "uuid4", lambda: UUID(value))


@pytest.mark.asyncio
async def test_enqueue_records_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = JobManager()
    enqueued_at = datetime(2025, 10, 21, 12, 0, tzinfo=UTC)

    _set_time_sequence(monkeypatch, enqueued_at)
    _freeze_uuid(monkeypatch, "12345678-1234-5678-1234-567812345678")

    entry = await manager.enqueue({"session_id": 1})

    assert entry["session_id"] == 1
    assert entry["task_id"] == "12345678-1234-5678-1234-567812345678"
    assert entry["status"] == "queued"
    assert entry["enqueued_at"] == enqueued_at
    assert entry["updated_at"] == enqueued_at
    assert entry["forced"] is False


@pytest.mark.asyncio
async def test_stop_stopped_updates_timestamp(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = JobManager()
    enqueued_at = datetime(2025, 10, 21, 12, 0, tzinfo=UTC)
    stopped_at = enqueued_at + timedelta(minutes=5)

    _set_time_sequence(monkeypatch, enqueued_at, stopped_at)
    _freeze_uuid(monkeypatch, "12345678-1234-5678-1234-567812345678")

    await manager.enqueue({"session_id": 7})
    entry = await manager.stop(7, reason="stopped")

    assert entry is not None
    assert entry["status"] == "stopped"
    assert entry["stopped_at"] == stopped_at
    assert entry["updated_at"] == stopped_at
    assert entry["forced"] is False


@pytest.mark.asyncio
async def test_stop_paused_tracks_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = JobManager()
    enqueued_at = datetime(2025, 10, 21, 12, 0, tzinfo=UTC)
    paused_at = enqueued_at + timedelta(minutes=2)

    _set_time_sequence(monkeypatch, enqueued_at, paused_at)
    _freeze_uuid(monkeypatch, "22345678-1234-5678-1234-567812345678")

    await manager.enqueue({"session_id": 11})
    entry = await manager.stop(11, reason="paused")

    assert entry is not None
    assert entry["status"] == "paused"
    assert entry["paused_at"] == paused_at
    assert entry["updated_at"] == paused_at
    assert entry["forced"] is False


@pytest.mark.asyncio
async def test_stop_revoked_marks_forced(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = JobManager()
    enqueued_at = datetime(2025, 10, 21, 12, 0, tzinfo=UTC)
    revoked_at = enqueued_at + timedelta(minutes=3)

    _set_time_sequence(monkeypatch, enqueued_at, revoked_at)
    _freeze_uuid(monkeypatch, "32345678-1234-5678-1234-567812345678")

    await manager.enqueue({"session_id": 21})
    entry = await manager.stop(21, reason="revoked")

    assert entry is not None
    assert entry["status"] == "revoked"
    assert entry["revoked_at"] == revoked_at
    assert entry["updated_at"] == revoked_at
    assert entry["forced"] is True


@pytest.mark.asyncio
async def test_resume_updates_status(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = JobManager()
    enqueued_at = datetime(2025, 10, 21, 12, 0, tzinfo=UTC)
    paused_at = enqueued_at + timedelta(minutes=4)
    resumed_at = paused_at + timedelta(minutes=6)

    _set_time_sequence(monkeypatch, enqueued_at, paused_at, resumed_at)
    _freeze_uuid(monkeypatch, "42345678-1234-5678-1234-567812345678")

    await manager.enqueue({"session_id": 42})
    await manager.stop(42, reason="paused")
    entry = await manager.resume(42)

    assert entry is not None
    assert entry["status"] == "queued"
    assert entry["resumed_at"] == resumed_at
    assert entry["updated_at"] == resumed_at
    assert entry["forced"] is False


@pytest.mark.asyncio
async def test_resume_missing_entry_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = JobManager()
    resumed_at = datetime(2025, 10, 21, 12, 0, tzinfo=UTC)

    _set_time_sequence(monkeypatch, resumed_at)

    assert await manager.resume(9999) is None
