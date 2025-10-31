"""Unit tests for Redis-backed WebSocket forwarding utilities."""

from __future__ import annotations

import asyncio
import json

import pytest

from app.core.websocket.manager import WebSocketManager


class FakeWebSocket:
  """Test double that mimics the minimal WebSocket interface."""

  def __init__(self) -> None:
    self.accepted = False
    self.closed = False
    self.sent_messages: list[dict[str, object]] = []

  async def accept(self) -> None:
    self.accepted = True

  async def send_json(self, message: dict[str, object]) -> None:
    self.sent_messages.append(message)

  async def close(self) -> None:
    self.closed = True


class FakePubSub:
  """Fake redis PubSub implementation for deterministic testing."""

  def __init__(self, messages: list[dict[str, object]]) -> None:
    self._messages: asyncio.Queue[dict[str, object]] = asyncio.Queue()
    for message in messages:
      self._messages.put_nowait(message)
    self.subscribed_channel: str | None = None
    self.unsubscribed_channel: str | None = None
    self.closed = False

  async def subscribe(self, channel: str) -> None:
    self.subscribed_channel = channel

  async def unsubscribe(self, channel: str) -> None:
    self.unsubscribed_channel = channel

  async def close(self) -> None:  # pragma: no cover - exercised implicitly
    self.closed = True

  async def get_message(self, *, timeout: float | None = None, ignore_subscribe_messages: bool = True) -> dict[str, object] | None:  # noqa: D401
    del ignore_subscribe_messages
    if timeout is not None and timeout <= 0:
      timeout = None
    try:
      if timeout is None:
        return await self._messages.get()
      return await asyncio.wait_for(self._messages.get(), timeout=timeout)
    except TimeoutError:
      return None


class FakeRedis:
  """Minimal redis client stub returning a prepared PubSub object."""

  def __init__(self, pubsub: FakePubSub) -> None:
    self._pubsub = pubsub

  def pubsub(self, *, ignore_subscribe_messages: bool = True) -> FakePubSub:
    del ignore_subscribe_messages
    return self._pubsub


@pytest.mark.asyncio
async def test_forwarder_broadcasts_messages_to_active_session() -> None:
  from app.core.websocket.redis_forwarder import RedisTrainingEventForwarder

  manager = WebSocketManager(heartbeat_interval=0.01)
  websocket = FakeWebSocket()
  await manager.connect(websocket, session_id=1)

  payload = {"type": "training_progress", "session_id": 1, "timestep": 5}
  pubsub = FakePubSub([
    {"type": "message", "data": json.dumps(payload)},
  ])
  redis = FakeRedis(pubsub)
  forwarder = RedisTrainingEventForwarder(redis_client=redis, websocket_manager=manager, poll_interval=0.01)

  await forwarder.ensure_session_listener(1)

  # Allow the background listener to process the queued message.
  await asyncio.sleep(0.05)

  assert websocket.sent_messages, "expected redis message to be forwarded to websocket clients"
  assert websocket.sent_messages[0]["type"] == "training_progress"

  await manager.disconnect(websocket, session_id=1)
  await forwarder.remove_session_listener(1)


@pytest.mark.asyncio
async def test_forwarder_reuses_existing_listener_task() -> None:
  from app.core.websocket.redis_forwarder import RedisTrainingEventForwarder

  manager = WebSocketManager(heartbeat_interval=0.01)
  websocket = FakeWebSocket()
  await manager.connect(websocket, session_id=2)

  redis = FakeRedis(FakePubSub([]))
  forwarder = RedisTrainingEventForwarder(redis_client=redis, websocket_manager=manager, poll_interval=0.01)

  await forwarder.ensure_session_listener(2)
  first_task = forwarder._tasks[2]

  await forwarder.ensure_session_listener(2)
  assert forwarder._tasks[2] is first_task

  await manager.disconnect(websocket, session_id=2)
  await forwarder.remove_session_listener(2)
