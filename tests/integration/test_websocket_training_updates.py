from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.websockets import WebSocketDisconnect

from app.api.deps import get_db
from app.api.v1.endpoints import websocket as websocket_endpoint_module
from app.core.websocket import manager as ws_manager_module
from app.core.websocket import redis_forwarder as redis_forwarder_module
from app.core.websocket.manager import WebSocketManager
from app.core.websocket.redis_forwarder import RedisTrainingEventForwarder
from app.db import database as db_module
from app.db import session as session_module
import app.main as main_module
from app.main import create_app
from app.models.training import TrainingJob
from fastapi.testclient import TestClient


class FakeRedisPubSub:
    def __init__(self, client: FakeRedisClient) -> None:
        self._client = client
        self._channels: list[str] = []
        self.closed = False

    async def subscribe(self, channel: str) -> None:
        self._client.ensure_queue(channel)
        if channel not in self._channels:
            self._channels.append(channel)

    async def get_message(
        self,
        *,
        ignore_subscribe_messages: bool = True,  # noqa: ARG002 - signature compatibility
        timeout: float = 0.0,
    ) -> dict[str, Any] | None:
        if not self._channels:
            raise RuntimeError("No channels subscribed")

        channel = self._channels[0]
        queue = self._client.ensure_queue(channel)
        try:
            payload = await asyncio.wait_for(queue.get(), timeout)
        except TimeoutError as exc:  # pragma: no cover - propagation to caller
            raise exc

        return {"type": "message", "data": payload}

    async def unsubscribe(self, channel: str) -> None:
        if channel in self._channels:
            self._channels.remove(channel)

    async def close(self) -> None:
        for channel in self._channels:
            self._client.mark_closed(channel)
        self._channels.clear()
        self.closed = True


class FakeRedisClient:
    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue[Any]] = {}
        self.closed_channels: set[str] = set()

    def ensure_queue(self, channel: str) -> asyncio.Queue[Any]:
        if channel not in self._queues:
            self._queues[channel] = asyncio.Queue()
        return self._queues[channel]

    def pubsub(self, *, ignore_subscribe_messages: bool = True) -> FakeRedisPubSub:  # noqa: ARG002
        return FakeRedisPubSub(self)

    async def publish(self, channel: str, message: Any) -> None:
        queue = self.ensure_queue(channel)
        await queue.put(message)

    def mark_closed(self, channel: str) -> None:
        self.closed_channels.add(channel)


@pytest.fixture()
def websocket_test_app(monkeypatch: pytest.MonkeyPatch):
    """Provide a FastAPI app wired to an in-memory database and fake Redis client."""

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    monkeypatch.setattr(db_module, "database_engine", engine)
    monkeypatch.setattr(main_module, "database_engine", engine)
    monkeypatch.setattr(session_module, "async_session", session_maker)

    test_manager = WebSocketManager(heartbeat_interval=0.05)
    monkeypatch.setattr(ws_manager_module, "websocket_manager", test_manager)
    monkeypatch.setattr(main_module, "websocket_manager", test_manager)
    monkeypatch.setattr(websocket_endpoint_module, "websocket_manager", test_manager)

    fake_redis = FakeRedisClient()
    forwarder = RedisTrainingEventForwarder(
        fake_redis,
        test_manager,
        poll_interval=0.05,
    )
    monkeypatch.setattr(redis_forwarder_module, "redis_forwarder", forwarder)
    monkeypatch.setattr(websocket_endpoint_module, "redis_forwarder", forwarder)

    app = create_app()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    yield app, fake_redis, session_maker

    app.dependency_overrides.clear()
    asyncio.run(engine.dispose())


async def _create_training_session(session_maker: async_sessionmaker[AsyncSession]) -> int:
    async with session_maker() as session:
        job = TrainingJob(
            name="Integration Session",
            algorithm="ppo",
            environment_type="standard",
            total_timesteps=1_000,
        )
        session.add(job)
        await session.flush()
        job_id = job.id
        await session.commit()
        return job_id


def test_websocket_forwards_redis_payload(websocket_test_app) -> None:
    app, fake_redis, session_maker = websocket_test_app

    with TestClient(app) as client:
        session_id = client.portal.call(_create_training_session, session_maker)

        with client.websocket_connect(f"/api/v1/ws/training/{session_id}") as websocket:
            ack = websocket.receive_json()
            assert ack["type"] == "connection_ack"
            assert ack["session_id"] == session_id
            assert ack["client_id"]

            client.portal.call(asyncio.sleep, 0.05)

            payload = {"episode": 1, "reward": 1.25}
            channel = RedisTrainingEventForwarder._channel_name(session_id)
            client.portal.call(fake_redis.publish, channel, payload)

            forwarded = websocket.receive_json()
            while forwarded.get("type") == "ping":
                forwarded = websocket.receive_json()
            assert forwarded["type"] == "training_progress"
            assert forwarded["session_id"] == session_id
            assert forwarded["episode"] == payload["episode"]
            assert forwarded["reward"] == payload["reward"]

        client.portal.call(asyncio.sleep, 0.1)

    forwarder_instance = redis_forwarder_module.redis_forwarder
    assert session_id not in forwarder_instance._tasks


def test_websocket_rejects_unknown_session(websocket_test_app) -> None:
    app, _, _ = websocket_test_app

    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect("/api/v1/ws/training/9999"):
                pass

        assert exc_info.value.code == 4404
        assert "session_not_found" in (exc_info.value.reason or "")
