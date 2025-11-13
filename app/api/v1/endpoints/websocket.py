"""WebSocket endpoints for real-time training updates."""

from __future__ import annotations

import json
import logging
from typing import Any
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.websocket.manager import websocket_manager
from app.core.websocket.redis_forwarder import redis_forwarder
from app.models.training import TrainingJob
from app.schemas.websocket import ConnectionAckMessage, PongMessage, TrainingErrorEvent
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

router = APIRouter()
logger = logging.getLogger(__name__)


async def _handle_client_message(
  message: dict[str, Any], websocket: WebSocket, session_id: int
) -> None:
  await websocket_manager.mark_seen(websocket)

  message_type = message.get("type")

  if message_type == "ping":
    await websocket_manager.send_personal_message(
      PongMessage().model_dump(mode="json"),
      websocket,
    )
  elif message_type in {"subscribe", "unsubscribe"}:
    # Placeholder for future granular subscriptions within a session.
    logger.debug("Ignoring noop subscription command: %s", message_type)
  else:
    error = TrainingErrorEvent(
      session_id=session_id,
      error_message=f"Unsupported message type: {message_type}",
      error_type="unsupported_message",
    )
    await websocket_manager.send_personal_message(
      error.model_dump(mode="json"),
      websocket,
    )


@router.websocket("/training/{session_id}")
async def training_updates(
  websocket: WebSocket,
  session_id: int,
  db: AsyncSession = Depends(get_db),
) -> None:
  """Stream training updates for a given session via WebSocket."""

  # Validate that the session exists before accepting the connection.
  result = await db.execute(select(TrainingJob.id).where(TrainingJob.id == session_id))
  if not result.scalar_one_or_none():
    logger.warning("WebSocket connection attempted for unknown session_id=%s", session_id)
    error = TrainingErrorEvent(
      session_id=session_id,
      error_message="Training session not found",
      error_type="session_not_found",
    )
    # Close with policy violation code to surface an explanatory reason without accepting.
    await websocket.close(code=4404, reason=error.model_dump_json())
    return

  client_id = str(uuid.uuid4())
  await websocket_manager.connect(websocket, session_id=session_id, client_id=client_id)
  await redis_forwarder.ensure_session_listener(session_id)

  ack = ConnectionAckMessage(client_id=client_id).model_dump(mode="json")
  ack["session_id"] = session_id
  await websocket_manager.send_personal_message(ack, websocket)

  try:
    while True:
      try:
        payload = await websocket.receive_text()
      except WebSocketDisconnect:
        raise
      except RuntimeError:
        # FastAPI raises RuntimeError when the connection is closed during receive.
        break

      try:
        message = json.loads(payload)
      except json.JSONDecodeError:
        logger.debug("Received non-JSON message from client: %s", payload)
        error = TrainingErrorEvent(
          session_id=session_id,
          error_message="Invalid JSON payload",
          error_type="invalid_payload",
        )
        await websocket_manager.send_personal_message(
          error.model_dump(mode="json"),
          websocket,
        )
        continue

      await _handle_client_message(message, websocket, session_id)

  except WebSocketDisconnect:
    logger.info("WebSocket client disconnected: session_id=%s client_id=%s", session_id, client_id)
  except Exception as exc:  # pragma: no cover - defensive logging
    logger.error("Unexpected WebSocket error", exc_info=exc)
    error = TrainingErrorEvent(
      session_id=session_id,
      error_message="Internal server error",
      error_type="internal_error",
    )
    await websocket_manager.send_personal_message(
      error.model_dump(mode="json"),
      websocket,
    )
  finally:
    await websocket_manager.disconnect(websocket, session_id)
    await redis_forwarder.release_session(session_id)
