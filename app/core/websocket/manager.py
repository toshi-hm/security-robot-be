"""WebSocket connection management utilities."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any

from app.core.config import settings
from app.schemas.websocket import PingMessage
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class WebSocketManager:
  """Manage WebSocket connections and scoped broadcasts."""

  def __init__(self, heartbeat_interval: float = 30.0) -> None:
    self.active_connections: list[WebSocket] = []
    self.session_connections: dict[int, list[WebSocket]] = defaultdict(list)
    self._connection_meta: dict[WebSocket, dict[str, Any]] = {}
    self._lock = asyncio.Lock()
    self._heartbeat_interval = heartbeat_interval
    self._heartbeat_task: asyncio.Task[None] | None = None
    self._running = False

  def start(self) -> None:
    """Start background bookkeeping for active WebSocket connections."""

    if self._running:
      return

    self._running = True

    try:
      loop = asyncio.get_running_loop()
    except RuntimeError:
      # Outside of an event loop (e.g. unit tests creating manager instances).
      logger.debug("WebSocketManager started without running loop; heartbeat disabled.")
      return

    self._heartbeat_task = loop.create_task(self._heartbeat_loop())
    logger.debug("WebSocketManager heartbeat task started.")

  def stop(self) -> None:
    """Stop background tasks and schedule graceful connection shutdown."""

    if not self._running:
      return

    self._running = False

    if self._heartbeat_task:
      self._heartbeat_task.cancel()
      self._heartbeat_task = None

    try:
      loop = asyncio.get_running_loop()
    except RuntimeError:
      # No loop available; best effort logging.
      logger.debug("WebSocketManager stopped without running loop; skipping cleanup scheduling.")
      return

    loop.create_task(self._close_all_connections())
    logger.debug("WebSocketManager cleanup task scheduled.")

  async def connect(
    self, websocket: WebSocket, session_id: int | None = None, *, client_id: str | None = None
  ) -> None:
    """Accept a WebSocket connection and track it for optional session scope."""

    await websocket.accept()

    async with self._lock:
      if websocket not in self.active_connections:
        self.active_connections.append(websocket)
      if session_id is not None:
        session_list = self.session_connections[session_id]
        if websocket not in session_list:
          session_list.append(websocket)

      metadata = self._connection_meta.setdefault(websocket, {})
      metadata["session_id"] = session_id
      metadata["client_id"] = client_id
      try:
        metadata["last_seen"] = asyncio.get_running_loop().time()
      except RuntimeError:
        metadata["last_seen"] = None

    logger.info(
      "WebSocket connected: session=%s total=%s client_id=%s",
      session_id,
      len(self.active_connections),
      client_id,
    )

  async def disconnect(self, websocket: WebSocket, session_id: int | None = None) -> None:
    """Remove a WebSocket connection from tracking and clean up metadata."""

    async with self._lock:
      if websocket in self.active_connections:
        self.active_connections.remove(websocket)

      if session_id is None:
        session_id = self._connection_meta.get(websocket, {}).get("session_id")

      if session_id is not None and session_id in self.session_connections:
        session_list = self.session_connections[session_id]
        if websocket in session_list:
          session_list.remove(websocket)
        if not session_list:
          del self.session_connections[session_id]

      self._connection_meta.pop(websocket, None)

    logger.info(
      "WebSocket disconnected: session=%s remaining=%s",
      session_id,
      len(self.active_connections),
    )

    # Close connection gracefully if still open.
    try:
      await websocket.close()
    except Exception:  # pragma: no cover - defensive cleanup
      logger.debug("WebSocket close raised; ignoring.")

  async def send_personal_message(self, message: dict[str, Any], websocket: WebSocket) -> None:
    """Send a message to a single WebSocket connection."""

    try:
      await websocket.send_json(message)
    except (RuntimeError, WebSocketDisconnect) as exc:
      logger.error("Failed to send personal message", exc_info=exc)
      await self.disconnect(websocket, self._connection_meta.get(websocket, {}).get("session_id"))
    except Exception as exc:  # pragma: no cover - unexpected transport errors
      logger.critical("Unexpected error while sending personal message", exc_info=exc)
      await self.disconnect(websocket, self._connection_meta.get(websocket, {}).get("session_id"))

  async def mark_seen(self, websocket: WebSocket) -> None:
    """Update last-seen timestamp for a connection."""

    try:
      last_seen = asyncio.get_running_loop().time()
    except RuntimeError:
      last_seen = None

    async with self._lock:
      if websocket in self._connection_meta:
        self._connection_meta[websocket]["last_seen"] = last_seen

  async def broadcast_to_session(self, session_id: int, message: dict[str, Any]) -> None:
    """Broadcast a message to all connections subscribed to a session."""

    async with self._lock:
      connections = list(self.session_connections.get(session_id, []))

    if not connections:
      return

    stale_connections: list[WebSocket] = []

    for connection in connections:
      try:
        await connection.send_json(message)
      except (RuntimeError, WebSocketDisconnect) as exc:
        logger.error("Failed to broadcast to session %s", session_id, exc_info=exc)
        stale_connections.append(connection)
      except Exception as exc:  # pragma: no cover - unexpected transport errors
        logger.critical("Unexpected error broadcasting to session %s", session_id, exc_info=exc)
        stale_connections.append(connection)

    for connection in stale_connections:
      await self.disconnect(connection, session_id)

  async def broadcast_all(self, message: dict[str, Any]) -> None:
    """Broadcast a message to every active connection."""

    async with self._lock:
      connections = list(self.active_connections)

    stale_connections: list[WebSocket] = []

    for connection in connections:
      try:
        await connection.send_json(message)
      except (RuntimeError, WebSocketDisconnect) as exc:
        logger.error("Failed to broadcast to all connections", exc_info=exc)
        stale_connections.append(connection)
      except Exception as exc:  # pragma: no cover - unexpected transport errors
        logger.critical("Unexpected error broadcasting to all connections", exc_info=exc)
        stale_connections.append(connection)

    for connection in stale_connections:
      await self.disconnect(connection, self._connection_meta.get(connection, {}).get("session_id"))

  async def _heartbeat_loop(self) -> None:
    """Periodically send heartbeat pings to keep connections alive."""

    try:
      while self._running:
        await asyncio.sleep(self._heartbeat_interval)
        await self._send_server_ping()
    except asyncio.CancelledError:  # pragma: no cover - cancellation control flow
      logger.debug("WebSocketManager heartbeat task cancelled.")

  async def _send_server_ping(self) -> None:
    if not self.active_connections:
      return

    payload = PingMessage().model_dump(mode="json")

    async with self._lock:
      connections = list(self.active_connections)

    stale_connections: list[WebSocket] = []

    for connection in connections:
      try:
        await connection.send_json(payload)
      except (RuntimeError, WebSocketDisconnect) as exc:
        logger.error("Failed to send heartbeat ping", exc_info=exc)
        stale_connections.append(connection)
      except Exception as exc:  # pragma: no cover - unexpected transport errors
        logger.critical("Unexpected error while sending heartbeat ping", exc_info=exc)
        stale_connections.append(connection)

    for connection in stale_connections:
      await self.disconnect(connection, self._connection_meta.get(connection, {}).get("session_id"))

  async def _close_all_connections(self) -> None:
    async with self._lock:
      connections = list(self.active_connections)

    for connection in connections:
      await self.disconnect(connection, self._connection_meta.get(connection, {}).get("session_id"))

  def has_connections(self, session_id: int) -> bool:
    """Return True if there are active WebSocket connections for the session."""

    return bool(self.session_connections.get(session_id))

  def get_connection_metadata(self, websocket: WebSocket) -> dict[str, Any]:
    """Return metadata tracked for a WebSocket connection."""

    return self._connection_meta.get(websocket, {}).copy()


websocket_manager = WebSocketManager(settings.websocket_heartbeat_interval)
