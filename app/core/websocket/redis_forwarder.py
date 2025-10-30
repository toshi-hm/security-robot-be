"""Redis Pub/Sub integration for training WebSocket streams."""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import suppress
from typing import Any

from redis import asyncio as redis_asyncio
from redis.exceptions import RedisError

from app.core.config import settings
from app.core.websocket.manager import WebSocketManager, websocket_manager

logger = logging.getLogger(__name__)


class RedisTrainingEventForwarder:
  """Forward training updates published on Redis channels to WebSocket clients."""

  def __init__(
    self,
    redis_client: redis_asyncio.Redis | Any,
    websocket_manager: WebSocketManager,
    poll_interval: float = 0.5,
  ) -> None:
    self._redis = redis_client
    self._manager = websocket_manager
    self._poll_interval = poll_interval
    self._tasks: dict[int, asyncio.Task[None]] = {}
    self._lock = asyncio.Lock()

  async def ensure_session_listener(self, session_id: int) -> None:
    """Ensure a listener task exists for the given training session."""

    async with self._lock:
      task = self._tasks.get(session_id)
      if task and not task.done():
        return

      task = asyncio.create_task(self._run_session_listener(session_id))
      self._tasks[session_id] = task

  async def remove_session_listener(self, session_id: int) -> None:
    """Cancel and remove the listener task for the given session if it exists."""

    async with self._lock:
      task = self._tasks.pop(session_id, None)

    if task:
      task.cancel()
      with suppress(asyncio.CancelledError):
        await task

  async def release_session(self, session_id: int) -> None:
    """Stop the listener when no WebSocket connections remain for the session."""

    if self._manager.has_connections(session_id):
      return

    await self.remove_session_listener(session_id)

  async def _run_session_listener(self, session_id: int) -> None:
    channel = self._channel_name(session_id)
    pubsub = None

    try:
      pubsub = self._redis.pubsub(ignore_subscribe_messages=True)
      await pubsub.subscribe(channel)

      while True:
        if not self._manager.has_connections(session_id):
          await asyncio.sleep(self._poll_interval)
          if not self._manager.has_connections(session_id):
            break

        try:
          message = await pubsub.get_message(
            ignore_subscribe_messages=True,
            timeout=self._poll_interval,
          )
        except TimeoutError:
          continue

        if not message or message.get("type") != "message":
          continue

        payload = self._parse_payload(message.get("data"), session_id)
        if payload is None:
          continue

        try:
          await self._manager.broadcast_to_session(session_id, payload)
        except Exception as exc:  # pragma: no cover - broadcast errors logged upstream
          logger.error("Failed to broadcast Redis payload", exc_info=exc)

    except asyncio.CancelledError:
      raise
    except RedisError as exc:
      logger.error("Redis error while listening on %s", channel, exc_info=exc)
    except Exception as exc:  # pragma: no cover - defensive logging
      logger.error("Unexpected error while forwarding Redis events", exc_info=exc)
    finally:
      if pubsub is not None:
        with suppress(Exception):
          await pubsub.unsubscribe(channel)
        with suppress(Exception):
          await pubsub.close()

      async with self._lock:
        task = self._tasks.get(session_id)
        if task and task.done():
          self._tasks.pop(session_id, None)

  def _parse_payload(self, data: Any, session_id: int) -> dict[str, Any] | None:
    if data is None:
      return None

    if isinstance(data, bytes):
      data = data.decode("utf-8")

    if isinstance(data, str):
      try:
        data = json.loads(data)
      except json.JSONDecodeError:
        logger.debug("Ignoring non-JSON payload for session %s", session_id)
        return None

    if not isinstance(data, dict):
      logger.debug("Ignoring non-dict payload for session %s: %r", session_id, data)
      return None

    if "type" not in data:
      data = {
        "type": "training_progress",
        "session_id": session_id,
        **data,
      }
    elif "session_id" not in data:
      data["session_id"] = session_id

    return data

  @staticmethod
  def _channel_name(session_id: int) -> str:
    return f"training_progress_{session_id}"


redis_forwarder = RedisTrainingEventForwarder(
  redis_client=redis_asyncio.from_url(settings.redis_url, decode_responses=False),
  websocket_manager=websocket_manager,
  poll_interval=0.5,
)

