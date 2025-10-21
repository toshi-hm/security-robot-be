"""Unit tests for the in-memory job queue manager."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from app.core.training import job_manager as job_manager_module
from app.core.training.job_manager import JobManager
from tests.utils.time import set_time_sequence


def _freeze_uuid(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    """Return a deterministic UUID string for queue entries."""

    monkeypatch.setattr(job_manager_module, "uuid4", lambda: UUID(value))


@pytest.mark.asyncio
async def test_enqueue_records_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = JobManager()
    enqueued_at = datetime(2025, 10, 21, 12, 0, tzinfo=UTC)

    set_time_sequence(monkeypatch, job_manager_module, enqueued_at)
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

    set_time_sequence(monkeypatch, job_manager_module, enqueued_at, stopped_at)
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

    set_time_sequence(monkeypatch, job_manager_module, enqueued_at, paused_at)
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

    set_time_sequence(monkeypatch, job_manager_module, enqueued_at, revoked_at)
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

    set_time_sequence(
        monkeypatch, job_manager_module, enqueued_at, paused_at, resumed_at
    )
    _freeze_uuid(monkeypatch, "42345678-1234-5678-1234-567812345678")

    await manager.enqueue({"session_id": 42})
    await manager.stop(42, reason="paused")
    entry = await manager.resume(42)

    assert entry is not None
    assert entry["status"] == "queued"
    assert entry["resumed_at"] == resumed_at
    assert entry["updated_at"] == resumed_at
    assert entry["forced"] is False
    # Stop-state timestamps should be cleared once the session has been
    # re-queued to avoid leaking stale metadata to API consumers.
    assert "paused_at" not in entry


@pytest.mark.asyncio
async def test_resume_missing_entry_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = JobManager()
    resumed_at = datetime(2025, 10, 21, 12, 0, tzinfo=UTC)

    set_time_sequence(monkeypatch, job_manager_module, resumed_at)

    result = await manager.resume(9999)

    assert result is None


@pytest.mark.asyncio
async def test_resume_after_revoked_clears_forced_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = JobManager()
    enqueued_at = datetime(2025, 10, 21, 12, 0, tzinfo=UTC)
    revoked_at = enqueued_at + timedelta(minutes=2)
    resumed_at = revoked_at + timedelta(minutes=5)

    set_time_sequence(
        monkeypatch, job_manager_module, enqueued_at, revoked_at, resumed_at
    )
    _freeze_uuid(monkeypatch, "52345678-1234-5678-1234-567812345678")

    await manager.enqueue({"session_id": 84})
    await manager.stop(84, reason="revoked")

    entry = await manager.resume(84)

    assert entry is not None
    assert entry["status"] == "queued"
    assert entry["forced"] is False
    assert entry["resumed_at"] == resumed_at
    assert entry["updated_at"] == resumed_at
    assert "revoked_at" not in entry


@pytest.mark.asyncio
async def test_stop_after_resume_preserves_resumed_timestamp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = JobManager()
    enqueued_at = datetime(2025, 10, 21, 12, 0, tzinfo=UTC)
    paused_at = enqueued_at + timedelta(minutes=2)
    resumed_at = paused_at + timedelta(minutes=4)
    stopped_again_at = resumed_at + timedelta(minutes=1)

    set_time_sequence(
        monkeypatch,
        job_manager_module,
        enqueued_at,
        paused_at,
        resumed_at,
        stopped_again_at,
    )
    _freeze_uuid(monkeypatch, "62345678-1234-5678-1234-567812345678")

    await manager.enqueue({"session_id": 128})
    await manager.stop(128, reason="paused")
    await manager.resume(128)

    entry = await manager.stop(128, reason="stopped")

    assert entry is not None
    assert entry["status"] == "stopped"
    assert entry["stopped_at"] == stopped_again_at
    assert entry["updated_at"] == stopped_again_at
    # The resume timestamp should remain to highlight the most recent resume
    # even after the session transitions into a terminal state.
    assert entry["resumed_at"] == resumed_at
    assert entry["forced"] is False


@pytest.mark.asyncio
async def test_discard_removes_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = JobManager()
    enqueued_at = datetime(2025, 10, 21, 12, 0, tzinfo=UTC)

    set_time_sequence(monkeypatch, job_manager_module, enqueued_at)

    await manager.enqueue({"session_id": 555})

    await manager.discard(555)

    assert manager.get(555) is None


@pytest.mark.asyncio
async def test_discard_nonexistent_entry_is_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = JobManager()
    enqueued_at = datetime(2025, 10, 21, 12, 0, tzinfo=UTC)

    set_time_sequence(monkeypatch, job_manager_module, enqueued_at)

    # Ensure discard does not raise and leaves the queue unchanged when the
    # session was never enqueued.
    await manager.discard(404)

    assert manager.snapshot() == []


@pytest.mark.asyncio
async def test_enqueue_missing_session_id_raises() -> None:
    manager = JobManager()

    with pytest.raises(ValueError, match="session_id"):
        await manager.enqueue({"task_id": "task-1"})


@pytest.mark.asyncio
async def test_stop_unknown_reason_preserves_forced(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = JobManager()
    enqueued_at = datetime(2025, 10, 21, 12, 0, tzinfo=UTC)
    paused_at = enqueued_at + timedelta(minutes=1)
    updated_at = paused_at + timedelta(minutes=1)

    set_time_sequence(
        monkeypatch, job_manager_module, enqueued_at, paused_at, updated_at
    )
    await manager.enqueue({"session_id": 55})
    await manager.stop(55, reason="revoked")

    entry = await manager.stop(55, reason="unknown_reason")

    assert entry is not None
    assert entry["status"] == "unknown_reason"
    assert entry["forced"] is True
    assert "revoked_at" not in entry
    assert entry["updated_at"] == updated_at


@pytest.mark.asyncio
async def test_stop_overwrites_previous_reason_timestamp(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = JobManager()
    enqueued_at = datetime(2025, 10, 21, 12, 0, tzinfo=UTC)
    paused_at = enqueued_at + timedelta(minutes=2)
    stopped_at = paused_at + timedelta(minutes=3)

    set_time_sequence(
        monkeypatch, job_manager_module, enqueued_at, paused_at, stopped_at
    )
    await manager.enqueue({"session_id": 77})
    await manager.stop(77, reason="paused")

    entry = await manager.stop(77, reason="stopped")

    assert entry is not None
    assert entry.get("stopped_at") == stopped_at
    assert "paused_at" not in entry


@pytest.mark.asyncio
async def test_stop_missing_entry_returns_none() -> None:
    manager = JobManager()

    result = await manager.stop(2024)

    assert result is None
    assert manager.snapshot() == []


@pytest.mark.asyncio
async def test_total_limit_prefers_purging_history(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = JobManager(max_active_entries=4, max_total_entries=5)
    base = datetime(2025, 10, 21, 12, 0, tzinfo=UTC)

    set_time_sequence(
        monkeypatch,
        job_manager_module,
        base,
        base + timedelta(minutes=1),
        base + timedelta(minutes=2),
        base + timedelta(minutes=3),
        base + timedelta(minutes=4),
        base + timedelta(minutes=5),
        base + timedelta(minutes=6),
        base + timedelta(minutes=7),
        base + timedelta(minutes=8),
    )

    await manager.enqueue({"session_id": 1})
    await manager.enqueue({"session_id": 2})
    await manager.enqueue({"session_id": 3})
    await manager.enqueue({"session_id": 4})
    await manager.stop(4, reason="stopped")
    await manager.enqueue({"session_id": 5})
    await manager.stop(5, reason="stopped")

    # Exceed the total limit by adding another history entry. The manager
    # should remove the oldest completed job (session 4) while keeping newer
    # history and all active entries intact.
    await manager.enqueue({"session_id": 6})
    await manager.stop(6, reason="stopped")

    assert manager.get(1) is not None
    assert manager.get(4) is None
    assert manager.get(5) is not None
    assert manager.get(6) is not None
    assert len(manager.snapshot()) == 5


@pytest.mark.asyncio
async def test_total_limit_purges_active_when_history_insufficient(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = JobManager(max_active_entries=10, max_total_entries=5)
    base = datetime(2025, 10, 21, 12, 0, tzinfo=UTC)

    timestamps = [base + timedelta(minutes=i) for i in range(6)]
    set_time_sequence(monkeypatch, job_manager_module, *timestamps)

    for session_id in range(1, 7):
        await manager.enqueue({"session_id": session_id})

    assert manager.get(1) is None
    assert manager.get(2) is not None
    assert len(manager.snapshot()) == 5


@pytest.mark.asyncio
async def test_active_limit_drops_oldest_active(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = JobManager(max_active_entries=2, max_total_entries=5)
    base = datetime(2025, 10, 21, 13, 0, tzinfo=UTC)

    set_time_sequence(
        monkeypatch,
        job_manager_module,
        base,
        base + timedelta(minutes=1),
        base + timedelta(minutes=2),
    )

    await manager.enqueue({"session_id": 10})
    await manager.enqueue({"session_id": 11})

    # Adding a third active session should prune the oldest active entry to
    # keep the queue within the configured active limit.
    await manager.enqueue({"session_id": 12})

    assert manager.get(10) is None
    assert manager.get(11) is not None
    assert manager.get(12) is not None
    assert len(manager.snapshot()) == 2


@pytest.mark.asyncio
async def test_history_ttl_sweep_removes_stale_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = JobManager(
        max_active_entries=3,
        max_total_entries=4,
        history_ttl=timedelta(minutes=30),
        sweep_interval=timedelta(minutes=5),
    )
    base = datetime(2025, 10, 21, 14, 0, tzinfo=UTC)

    set_time_sequence(
        monkeypatch,
        job_manager_module,
        base,
        base + timedelta(minutes=10),
        base + timedelta(minutes=46),
    )

    await manager.enqueue({"session_id": 20})
    await manager.stop(20, reason="stopped")

    # Trigger retention checks long after the TTL has elapsed to sweep the
    # stale history entry.
    await manager.enqueue({"session_id": 21})

    assert manager.get(20) is None
    assert manager.get(21) is not None
    assert len(manager.snapshot()) == 1


@pytest.mark.asyncio
async def test_sweep_respects_interval(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = JobManager(
        max_active_entries=3,
        max_total_entries=4,
        history_ttl=timedelta(minutes=10),
        sweep_interval=timedelta(minutes=5),
    )
    base = datetime(2025, 10, 21, 14, 0, tzinfo=UTC)

    set_time_sequence(
        monkeypatch,
        job_manager_module,
        base,
        base + timedelta(minutes=1),
        base + timedelta(minutes=10),
        base + timedelta(minutes=14),
    )

    await manager.enqueue({"session_id": 1})
    await manager.stop(1, reason="stopped")

    # Refresh the sweep timestamp shortly before the TTL would expire so the
    # next operation occurs within the sweep interval window.
    await manager.enqueue({"session_id": 2})

    await manager.enqueue({"session_id": 3})

    assert manager.get(1) is not None


@pytest.mark.asyncio
async def test_sweep_disabled_when_ttl_non_positive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = JobManager(
        max_active_entries=3,
        max_total_entries=4,
        history_ttl=timedelta(0),
        sweep_interval=timedelta(minutes=5),
    )
    base = datetime(2025, 10, 21, 15, 0, tzinfo=UTC)

    set_time_sequence(
        monkeypatch,
        job_manager_module,
        base,
        base + timedelta(minutes=1),
        base + timedelta(minutes=30),
    )

    await manager.enqueue({"session_id": 1})
    await manager.stop(1, reason="stopped")

    await manager.enqueue({"session_id": 2})

    assert manager.get(1) is not None
    assert len(manager.snapshot()) == 2
