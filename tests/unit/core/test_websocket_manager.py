import asyncio
from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio

from app.core.websocket.manager import WebSocketManager


class FakeWebSocket:
    """Minimal async test double for Starlette's WebSocket."""

    def __init__(self) -> None:
        self.accepted = False
        self.closed = False
        self.sent_messages: list[dict[str, Any]] = []

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, message: dict[str, Any]) -> None:
        self.sent_messages.append(message)

    async def close(self) -> None:
        self.closed = True


class FailingWebSocket(FakeWebSocket):
    async def send_json(self, message: dict[str, Any]) -> None:  # type: ignore[override]
        raise RuntimeError("connection lost")


@pytest_asyncio.fixture
async def manager() -> AsyncIterator[WebSocketManager]:
    manager = WebSocketManager(heartbeat_interval=0.01)
    manager.start()
    try:
        yield manager
    finally:
        manager.stop()
        # Allow cancellation and cleanup tasks to run to completion.
        await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_connect_and_disconnect_tracks_sessions(manager: WebSocketManager) -> None:
    websocket = FakeWebSocket()

    await manager.connect(websocket, session_id=1, client_id="client-1")

    assert websocket in manager.active_connections
    assert websocket in manager.session_connections[1]
    assert websocket.accepted is True

    await manager.disconnect(websocket, session_id=1)

    assert websocket not in manager.active_connections
    assert 1 not in manager.session_connections
    assert websocket.closed is True


@pytest.mark.asyncio
async def test_broadcast_to_session_only_targets_matching_connections(manager: WebSocketManager) -> None:
    session_websocket = FakeWebSocket()
    other_websocket = FakeWebSocket()

    await manager.connect(session_websocket, session_id=5)
    await manager.connect(other_websocket, session_id=7)

    payload = {"type": "test", "value": 123}
    await manager.broadcast_to_session(5, payload)

    assert payload in session_websocket.sent_messages
    assert other_websocket.sent_messages == []


@pytest.mark.asyncio
async def test_broadcast_to_session_removes_failed_connections(manager: WebSocketManager) -> None:
    flaky_websocket = FailingWebSocket()
    healthy_websocket = FakeWebSocket()

    await manager.connect(flaky_websocket, session_id=9)
    await manager.connect(healthy_websocket, session_id=9)

    await manager.broadcast_to_session(9, {"type": "progress"})

    assert flaky_websocket not in manager.active_connections
    assert healthy_websocket in manager.active_connections
    assert healthy_websocket.sent_messages == [{"type": "progress"}]


@pytest.mark.asyncio
async def test_mark_seen_updates_last_seen(manager: WebSocketManager) -> None:
    websocket = FakeWebSocket()

    await manager.connect(websocket, session_id=42)

    before = manager.get_connection_metadata(websocket)["last_seen"]

    await asyncio.sleep(0)
    await manager.mark_seen(websocket)

    after = manager.get_connection_metadata(websocket)["last_seen"]

    assert after is not None
    assert after != before


@pytest.mark.asyncio
async def test_broadcast_all_reaches_everyone(manager: WebSocketManager) -> None:
    first = FakeWebSocket()
    second = FakeWebSocket()

    await manager.connect(first, session_id=1)
    await manager.connect(second, session_id=2)

    payload = {"type": "announcement"}
    await manager.broadcast_all(payload)

    assert payload in first.sent_messages
    assert payload in second.sent_messages


@pytest.mark.asyncio
async def test_send_server_ping_uses_ping_schema(manager: WebSocketManager) -> None:
    websocket = FakeWebSocket()

    await manager.connect(websocket, session_id=100)

    await manager._send_server_ping()

    assert websocket.sent_messages
    assert websocket.sent_messages[-1]["type"] == "ping"


@pytest.mark.asyncio
async def test_get_connection_metadata_returns_copy(manager: WebSocketManager) -> None:
    websocket = FakeWebSocket()

    await manager.connect(websocket, session_id=7, client_id="client-7")

    metadata = manager.get_connection_metadata(websocket)

    assert metadata["session_id"] == 7
    assert metadata["client_id"] == "client-7"

    metadata["client_id"] = "mutated"

    assert manager.get_connection_metadata(websocket)["client_id"] == "client-7"
