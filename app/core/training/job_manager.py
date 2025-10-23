from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, AsyncIterator, Callable, Literal

from uuid import uuid4

from app.utils.datetime import utcnow


StopReason = Literal["stopped", "paused", "revoked"]


@dataclass
class _SessionLock:
    """Container that tracks per-session lock usage."""

    lock: asyncio.Lock
    users: int = 0


class JobManager:
    """Lightweight in-memory queue manager used for API integration tests."""

    _STOP_REASON_KEYS = ("stopped_at", "paused_at", "revoked_at")
    _DEFAULT_TIMESTAMP = datetime.min.replace(tzinfo=UTC)

    def __init__(
        self,
        *,
        max_active_entries: int = 200,
        max_total_entries: int = 500,
        history_ttl: timedelta = timedelta(minutes=30),
        sweep_interval: timedelta = timedelta(minutes=5),
        lock_factory: Callable[[], asyncio.Lock] | None = None,
    ) -> None:
        self._jobs: dict[int, dict[str, Any]] = {}
        self._max_active_entries = max_active_entries
        self._max_total_entries = max_total_entries
        self._history_ttl = history_ttl
        self._sweep_interval = sweep_interval
        self._last_sweep_at: datetime | None = None
        self._lock_factory = lock_factory or asyncio.Lock
        self._locks: dict[int, _SessionLock] = {}

    def _get_lock(self, session_id: int) -> _SessionLock:
        """Return the session-scoped lock creating it on first access."""

        return self._locks.setdefault(
            session_id, _SessionLock(lock=self._lock_factory())
        )

    @asynccontextmanager
    async def _session_guard(self, session_id: int) -> AsyncIterator[None]:
        """Acquire the per-session lock while tracking active waiters."""

        lock_entry = self._get_lock(session_id)
        lock_entry.users += 1
        try:
            async with lock_entry.lock:
                yield
        finally:
            lock_entry.users -= 1
            if lock_entry.users < 0:
                lock_entry.users = 0
                raise RuntimeError("Session lock usage counter underflow")
            self._cleanup_lock_if_unused(session_id)

    def _cleanup_lock_if_unused(self, session_id: int) -> None:
        """Remove the session lock once no jobs or waiters remain for it."""

        lock_entry = self._locks.get(session_id)
        if lock_entry is None:
            return

        if session_id in self._jobs:
            return

        if lock_entry.users > 0:
            return

        if lock_entry.lock.locked():
            return

        self._locks.pop(session_id, None)

    def _enforce_limits(self, now: datetime) -> None:
        """Run retention checks to keep the queue within memory bounds."""

        self._maybe_sweep_expired(now)
        self._prune_counts()

    def _maybe_sweep_expired(self, now: datetime) -> None:
        """Drop history entries that exceeded their TTL on the configured cadence."""

        if self._history_ttl <= timedelta(0):
            return

        if (
            self._last_sweep_at is not None
            and now - self._last_sweep_at < self._sweep_interval
        ):
            return

        cutoff = now - self._history_ttl
        for session_id, entry in list(self._jobs.items()):
            if self._is_active(entry):
                continue

            updated_at = entry.get("updated_at")
            if updated_at is None:
                continue

            if updated_at <= cutoff:
                self._jobs.pop(session_id, None)
                self._cleanup_lock_if_unused(session_id)

        self._last_sweep_at = now

    def _prune_counts(self) -> None:
        """Ensure active and total queue sizes stay within configured limits."""

        def _partition() -> tuple[list[tuple[int, dict[str, Any]]], list[tuple[int, dict[str, Any]]]]:
            active: list[tuple[int, dict[str, Any]]] = []
            history: list[tuple[int, dict[str, Any]]] = []

            for session_id, entry in self._jobs.items():
                if self._is_active(entry):
                    active.append((session_id, entry))
                else:
                    history.append((session_id, entry))

            return active, history

        def _sort_key(item: tuple[int, dict[str, Any]]) -> tuple[datetime, datetime]:
            entry = item[1]
            updated_at = entry.get("updated_at") or entry.get("enqueued_at")
            if updated_at is None:
                updated_at = self._DEFAULT_TIMESTAMP
            enqueued_at = entry.get("enqueued_at") or updated_at
            return (updated_at, enqueued_at)

        active, history = _partition()
        if not active and not history:
            return

        sorted_active: list[tuple[int, dict[str, Any]]] | None = None
        sorted_history: list[tuple[int, dict[str, Any]]] | None = None

        if len(active) > self._max_active_entries:
            sorted_active = sorted(active, key=_sort_key)
            excess = len(active) - self._max_active_entries
            to_remove = sorted_active[:excess]
            for session_id, _ in to_remove:
                self._jobs.pop(session_id, None)
                self._cleanup_lock_if_unused(session_id)
            active = sorted_active[excess:]
            sorted_active = active

        total = len(active) + len(history)
        if total <= self._max_total_entries:
            return

        excess_total = total - self._max_total_entries

        if history:
            if sorted_history is None:
                sorted_history = sorted(history, key=_sort_key)
            remove_count = min(excess_total, len(sorted_history))
            for session_id, _ in sorted_history[:remove_count]:
                self._jobs.pop(session_id, None)
                self._cleanup_lock_if_unused(session_id)
            history = sorted_history[remove_count:]
            sorted_history = history
            excess_total -= remove_count

        if excess_total <= 0:
            return

        if not active:
            return

        if sorted_active is None:
            sorted_active = sorted(active, key=_sort_key)

        for session_id, _ in sorted_active[:excess_total]:
            self._jobs.pop(session_id, None)
            self._cleanup_lock_if_unused(session_id)

    def _is_active(self, entry: dict[str, Any]) -> bool:
        """Return whether a job entry represents an active session."""

        return entry.get("status") in {"queued", "running", "paused"}

    async def enqueue(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Register a training job request and return queue metadata."""

        session_id = payload.get("session_id")
        if session_id is None:
            raise ValueError("payload must include a session_id")

        async with self._session_guard(session_id):
            task_id = payload.get("task_id") or str(uuid4())
            timestamp = utcnow()
            metadata = {
                "session_id": session_id,
                "task_id": task_id,
                "status": "queued",
                "payload": payload,
                "enqueued_at": timestamp,
                "updated_at": timestamp,
                "forced": False,
            }
            self._jobs[session_id] = metadata
            self._enforce_limits(timestamp)
            return metadata

    async def stop(
        self, session_id: int, *, reason: StopReason | str = "stopped"
    ) -> dict[str, Any] | None:
        """Update the queue entry to reflect a paused or stopped state.

        Stop-reason timestamps from earlier transitions are cleared while the most
        recent ``resumed_at`` value (when present) is preserved so downstream
        consumers can still observe the resume→stop timeline. The resume timestamp
        is stashed before metadata cleanup to ensure it survives even if the
        cleanup routine expands to cover additional fields.
        """

        async with self._session_guard(session_id):
            entry = self._jobs.get(session_id)
            if entry is None:
                result: dict[str, Any] | None = None
            else:
                timestamp = utcnow()
                entry["status"] = reason
                entry["updated_at"] = timestamp

                resume_timestamp = entry.pop("resumed_at", None)

                # Remove stale stop-state timestamps before recording the latest
                # reason.
                self._clear_stop_timestamps(entry)

                if resume_timestamp is not None:
                    entry["resumed_at"] = resume_timestamp

                if reason == "stopped":
                    entry["stopped_at"] = timestamp
                    entry["forced"] = False
                elif reason == "paused":
                    entry["paused_at"] = timestamp
                    entry["forced"] = False
                elif reason == "revoked":
                    entry["revoked_at"] = timestamp
                    entry["forced"] = True
                else:
                    entry["forced"] = entry.get("forced", False)

                self._enforce_limits(timestamp)
                result = entry

        return result

    async def resume(self, session_id: int) -> dict[str, Any] | None:
        """Resume a paused session by marking it as queued again."""

        async with self._session_guard(session_id):
            entry = self._jobs.get(session_id)
            if entry is None:
                result: dict[str, Any] | None = None
            else:
                timestamp = utcnow()
                entry["status"] = "queued"
                entry["resumed_at"] = timestamp
                entry["updated_at"] = timestamp
                entry["forced"] = False
                self._clear_stop_timestamps(entry)
                self._enforce_limits(timestamp)
                result = entry

        return result

    def _clear_stop_timestamps(self, entry: dict[str, Any]) -> None:
        """Remove all stop-reason timestamps from the entry."""

        for key in self._STOP_REASON_KEYS:
            entry.pop(key, None)

    async def discard(self, session_id: int) -> None:
        """Remove a session from the queue manager."""

        async with self._session_guard(session_id):
            self._jobs.pop(session_id, None)

    def get(self, session_id: int) -> dict[str, Any] | None:
        """Return the queue entry for a specific session."""

        return self._jobs.get(session_id)

    def snapshot(self) -> list[dict[str, Any]]:
        """Return a snapshot of the known job queue state."""

        return list(self._jobs.values())


job_manager = JobManager()
