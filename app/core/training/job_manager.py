from __future__ import annotations

from typing import Any, Literal

from uuid import uuid4

from app.utils.datetime import utcnow


StopReason = Literal["stopped", "paused", "revoked"]


class JobManager:
    """Lightweight in-memory queue manager used for API integration tests."""

    def __init__(self) -> None:
        self._jobs: dict[int, dict[str, Any]] = {}

    async def enqueue(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Register a training job request and return queue metadata."""

        session_id = payload.get("session_id")
        if session_id is None:
            raise ValueError("payload must include a session_id")

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
        return metadata

    async def stop(
        self, session_id: int, *, reason: StopReason | str = "stopped"
    ) -> dict[str, Any] | None:
        """Update the queue entry to reflect a paused or stopped state.

        Only the timestamp associated with the latest ``reason`` is retained so the
        metadata mirrors the current queue state rather than the full history.
        """

        entry = self._jobs.get(session_id)
        if entry is None:
            return None

        timestamp = utcnow()
        entry["status"] = reason
        entry["updated_at"] = timestamp

        # Remove stale stop-state timestamps before recording the latest reason.
        for key in ("stopped_at", "paused_at", "revoked_at"):
            entry.pop(key, None)

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

        return entry

    async def resume(self, session_id: int) -> dict[str, Any] | None:
        """Resume a paused session by marking it as queued again."""

        entry = self._jobs.get(session_id)
        if entry is None:
            return None

        timestamp = utcnow()
        entry["status"] = "queued"
        entry["resumed_at"] = timestamp
        entry["updated_at"] = timestamp
        entry["forced"] = False
        for key in ("stopped_at", "paused_at", "revoked_at"):
            entry.pop(key, None)
        return entry

    async def discard(self, session_id: int) -> None:
        """Remove a session from the queue manager."""

        self._jobs.pop(session_id, None)

    def get(self, session_id: int) -> dict[str, Any] | None:
        """Return the queue entry for a specific session."""

        return self._jobs.get(session_id)

    def snapshot(self) -> list[dict[str, Any]]:
        """Return a snapshot of the known job queue state."""

        return list(self._jobs.values())


job_manager = JobManager()
