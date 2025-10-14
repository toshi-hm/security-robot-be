import json
from types import SimpleNamespace

import pytest

from rl.callbacks.redis_pubsub_callback import RedisTrainingCallback


class _DummyRedis:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []

    def publish(self, channel: str, message: str) -> None:
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
