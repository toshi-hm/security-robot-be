from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from rl.utils import evaluation


class _ActionSpace:
  def sample(self) -> int:  # pragma: no cover - used indirectly
    return 0


@dataclass
class _Spec:
  factory: Any

  def create(self, **overrides: Any) -> Any:
    return self.factory(**overrides)


class CoverageEnv:
  def __init__(self) -> None:
    self.action_space = _ActionSpace()
    self.coverage_history: list[float] = []
    self._steps = 0

  def reset(self, *, seed: int | None = None):
    self._steps = 0
    self.coverage_history.clear()
    return None, {}

  def step(self, action: int):
    self._steps += 1
    terminated = self._steps >= 3
    self.coverage_history.append(0.3 + 0.1 * self._steps)
    return None, 1.0, terminated, False, {"step": self._steps}


class NoCoverageEnv:
  def __init__(self) -> None:
    self.action_space = _ActionSpace()
    self._steps = 0

  def reset(self, *, seed: int | None = None):
    self._steps = 0
    return None, {}

  def step(self, action: int):
    self._steps += 1
    terminated = self._steps >= 2
    return None, 2.0, terminated, False, {}


def test_evaluate_model_includes_coverage(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setattr(
    evaluation,
    "get_environment_spec",
    lambda environment_id: _Spec(factory=lambda **_: CoverageEnv()),
  )

  result = evaluation.evaluate_model("model.pt", episodes=2, max_steps=5, seed=1)

  assert result["episodes"] == 2
  assert result["average_reward"] == pytest.approx(3.0)
  assert result["average_coverage_ratio"] == pytest.approx(0.6)


def test_evaluate_model_without_coverage(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setattr(
    evaluation,
    "get_environment_spec",
    lambda environment_id: _Spec(factory=lambda **_: NoCoverageEnv()),
  )

  result = evaluation.evaluate_model("model.pt", episodes=1, max_steps=3)

  assert result["episodes"] == 1
  assert "average_coverage_ratio" not in result
  assert result["average_reward"] == pytest.approx(4.0)
