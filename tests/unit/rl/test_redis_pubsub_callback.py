import json
from types import SimpleNamespace

import pytest
from redis.exceptions import RedisError

from app.models.training import TrainingJobStatus
from rl.callbacks.redis_pubsub_callback import RedisTrainingCallback, TrainingCancelled


class _DummyRedis:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []

    def publish(self, channel: str, message: str) -> None:
        self.messages.append((channel, message))


class _FlakyRedis:
    def __init__(self, outcomes: list[str]) -> None:
        self.outcomes = outcomes
        self.messages: list[tuple[str, str]] = []
        self.attempts = 0

    def publish(self, channel: str, message: str) -> None:
        self.attempts += 1
        outcome = self.outcomes.pop(0) if self.outcomes else "success"
        if outcome == "error":
            raise RedisError("publish failed")
        self.messages.append((channel, message))


def test_redis_callback_publishes_progress_and_status() -> None:
    redis = _DummyRedis()
    states: list[dict[str, object]] = []
    callback = RedisTrainingCallback(
        session_id=1,
        redis_client=redis,
        update_interval=2,
        total_timesteps=10,
        state_hook=lambda meta: states.append(meta),
    )

    callback.model = SimpleNamespace(
        logger=SimpleNamespace(name_to_value={"train/loss": 0.5})
    )

    callback._on_training_start()

    callback.locals = {"rewards": [1.0], "dones": [False]}
    callback.num_timesteps = 1
    callback.n_calls = 1
    assert callback._on_step() is True

    callback.locals = {"rewards": [2.0], "dones": [True]}
    callback.num_timesteps = 2
    callback.n_calls = 2
    assert callback._on_step() is True

    callback._on_training_end()

    assert len(redis.messages) == 3

    start_channel, start_payload = redis.messages[0]
    assert start_channel == "training_progress_1"
    assert json.loads(start_payload)["type"] == "training_status"

    progress_channel, progress_payload = redis.messages[1]
    assert progress_channel == "training_progress_1"
    progress = json.loads(progress_payload)
    assert progress["type"] == "training_progress"
    assert progress["timestep"] == 2
    assert pytest.approx(progress["reward"]) == 3.0
    assert progress["additional_metrics"]["total_episodes"] == 1
    assert progress["additional_metrics"]["episode_length"] == 2
    assert progress["loss"] == pytest.approx(0.5)

    end_channel, end_payload = redis.messages[2]
    assert end_channel == "training_progress_1"
    assert json.loads(end_payload)["status"] == "completed"

    assert len(states) == 3
    assert states[0]["status"] == "running"
    assert states[1]["current"] == 2
    assert pytest.approx(states[1]["progress"]) == pytest.approx(0.2)
    assert states[2]["status"] == "completed"


def test_redis_callback_retries_critical_status() -> None:
    redis = _FlakyRedis(["success", "error", "error", "success"])
    callback = RedisTrainingCallback(
        session_id=42,
        redis_client=redis,
        update_interval=5,
    )

    callback._on_training_start()
    callback._on_training_end()

    assert redis.attempts == 4
    assert len(redis.messages) == 2
    types = [json.loads(message)["type"] for _, message in redis.messages]
    assert types == ["training_status", "training_status"]
    statuses = [json.loads(message)["status"] for _, message in redis.messages]
    assert statuses[-1] == "completed"


def test_redis_callback_raises_when_job_paused() -> None:
    redis = _DummyRedis()
    states: list[dict[str, object]] = []

    def status_getter() -> TrainingJobStatus:
        return TrainingJobStatus.paused

    callback = RedisTrainingCallback(
        session_id=7,
        redis_client=redis,
        update_interval=1,
        total_timesteps=100,
        state_hook=lambda meta: states.append(meta),
        status_getter=status_getter,
        status_check_interval=1,
    )

    callback.model = SimpleNamespace(logger=SimpleNamespace(name_to_value={}))

    callback._on_training_start()

    callback.locals = {"rewards": [0.0], "dones": [False]}
    callback.n_calls = 1
    callback.num_timesteps = 1

    with pytest.raises(TrainingCancelled):
        callback._on_step()

    _, payload = redis.messages[-1]
    assert json.loads(payload)["status"] == "paused"
    assert states[-1]["status"] == "paused"
