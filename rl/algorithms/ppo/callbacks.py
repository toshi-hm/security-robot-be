from typing import Protocol


class TrainingCallback(Protocol):
  def __call__(self, step: int, reward: float) -> None: ...
