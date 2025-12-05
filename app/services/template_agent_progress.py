"""Utilities for broadcasting template agent execution progress over WebSocket."""

from __future__ import annotations

import asyncio
from collections import defaultdict
import logging
from typing import Any

import anyio
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class TemplateAgentProgressManager:
  """Tracks WebSocket connections per execution and broadcasts progress events."""

  def __init__(self) -> None:
    self._connections: dict[str, set[WebSocket]] = defaultdict(set)
    self._lock = asyncio.Lock()

  async def connect(self, execution_id: str, websocket: WebSocket) -> None:
    await websocket.accept()
    async with self._lock:
      self._connections[execution_id].add(websocket)
    logger.info("Template agent WebSocket connected: execution_id=%s", execution_id)

  async def disconnect(self, execution_id: str, websocket: WebSocket) -> None:
    async with self._lock:
      connections = self._connections.get(execution_id)
      if not connections:
        return
      connections.discard(websocket)
      if not connections:
        self._connections.pop(execution_id, None)
    logger.info("Template agent WebSocket disconnected: execution_id=%s", execution_id)

  async def broadcast(self, execution_id: str, message: dict[str, Any]) -> None:
    async with self._lock:
      targets = list(self._connections.get(execution_id, set()))

    for connection in targets:
      try:
        await connection.send_json(message)
      except WebSocketDisconnect:
        await self.disconnect(execution_id, connection)
      except RuntimeError:
        await self.disconnect(execution_id, connection)


class TemplateAgentProgressPublisher:
  """Callable helper that pushes dict messages to the async progress manager."""

  def __init__(
    self,
    execution_id: str,
    manager: TemplateAgentProgressManager,
  ) -> None:
    self._execution_id = execution_id
    self._manager = manager

  def __call__(self, message: dict[str, Any]) -> None:
    payload = {"execution_id": self._execution_id, **message}
    anyio.from_thread.run(self._manager.broadcast, self._execution_id, payload)


template_agent_progress_manager = TemplateAgentProgressManager()
