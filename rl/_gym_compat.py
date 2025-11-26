"""Compatibility layer for an optional Gymnasium dependency."""

from __future__ import annotations

from dataclasses import dataclass
import importlib
import importlib.util
import random
from typing import Any

_SPEC = importlib.util.find_spec("gymnasium")

if _SPEC is not None:  # pragma: no cover - exercised when gymnasium is installed
  gym = importlib.import_module("gymnasium")
  spaces = gym.spaces
else:

  class _Env:
    """Minimal stand-in for :class:`gymnasium.Env`."""

    metadata: dict[str, Any] = {}

    def __init__(self, *args: Any, **kwargs: Any) -> None:
      self.np_random = random.Random()

    def reset(
      self,
      *,
      seed: int | None = None,
      options: dict[str, Any] | None = None,
    ) -> tuple[Any, dict[str, Any]]:
      if seed is not None:
        self.np_random.seed(seed)
        random.seed(seed)
      return None, {}

    def step(self, action: Any) -> tuple[Any, float, bool, bool, dict[str, Any]]:
      raise NotImplementedError("Fallback Env does not implement step().")

    def render(self, mode: str = "human") -> None:  # pragma: no cover - noop
      return None

  @dataclass(slots=True)
  class _Box:
    """Lightweight variant of :class:`gymnasium.spaces.Box`."""

    low: Any
    high: Any
    shape: tuple[int, ...]
    dtype: Any = float

    def _expand(self, value: Any) -> tuple[float, ...]:
      if isinstance(value, tuple | list):
        return tuple(float(v) for v in value)
      return (float(value),) * len(self.shape)

    def sample(self) -> list[Any]:
      lows = self._expand(self.low)
      highs = self._expand(self.high)

      def _sample_dimension(idx: int, dims: tuple[int, ...]) -> Any:
        if not dims:
          span_low = lows[min(idx, len(lows) - 1)]
          span_high = highs[min(idx, len(highs) - 1)]
          return random.uniform(span_low, span_high)

        return [_sample_dimension(idx + 1, dims[1:]) for _ in range(dims[0])]

      return _sample_dimension(0, self.shape)  # type: ignore[no-any-return]

  @dataclass(slots=True)
  class _Discrete:
    """Minimal :class:`gymnasium.spaces.Discrete` alternative."""

    n: int

    def __post_init__(self) -> None:
      if self.n <= 0:
        msg = "Discrete space size must be positive."
        raise ValueError(msg)

    def sample(self) -> int:
      return random.randrange(self.n)

  class _SpacesModule:
    Box = _Box
    Discrete = _Discrete

  class _GymModule:
    Env = _Env

  gym = _GymModule()  # type: ignore[assignment]
  spaces = _SpacesModule()


__all__ = ["gym", "spaces"]
