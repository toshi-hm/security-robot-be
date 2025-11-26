"""Tests for template agent WebSocket progress utilities."""

from __future__ import annotations

import anyio
import pytest

from app.services.template_agent_progress import (
  TemplateAgentProgressManager,
  TemplateAgentProgressPublisher,
)


class DummyWebSocket:
  """Minimal WebSocket stub used for unit tests."""

  def __init__(self) -> None:
    self.accepted = False
    self.messages: list[dict] = []

  async def accept(self) -> None:
    self.accepted = True

  async def send_json(self, payload: dict) -> None:
    self.messages.append(payload)


@pytest.mark.asyncio
async def test_broadcast_delivers_messages() -> None:
  manager = TemplateAgentProgressManager()
  websocket = DummyWebSocket()

  await manager.connect("exec-1", websocket)  # type: ignore[arg-type]
  await manager.broadcast("exec-1", {"type": "ping"})

  assert websocket.accepted is True
  assert websocket.messages[-1]["type"] == "ping"


@pytest.mark.asyncio
async def test_publisher_includes_execution_id() -> None:
  manager = TemplateAgentProgressManager()
  websocket = DummyWebSocket()
  await manager.connect("exec-2", websocket)  # type: ignore[arg-type]

  publisher = TemplateAgentProgressPublisher("exec-2", manager)
  await anyio.to_thread.run_sync(publisher, {"type": "episode_started", "episode": 1})

  assert websocket.messages[-1]["execution_id"] == "exec-2"
  assert websocket.messages[-1]["episode"] == 1
