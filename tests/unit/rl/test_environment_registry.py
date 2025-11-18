from __future__ import annotations

import pytest

from rl.environments import EnvironmentSpec, available_environments, get_environment_spec


def test_environment_spec_create_merges_overrides() -> None:
  class _Env:
    def __init__(self, *, width: int, custom: int) -> None:
      self.width = width
      self.custom = custom

  spec = EnvironmentSpec(
    id="test",
    name="Test",
    description="",
    factory=_Env,
    default_config={"width": 5, "custom": 1},
  )

  env = spec.create(custom=9)
  assert env.width == 5
  assert env.custom == 9


def test_get_environment_spec() -> None:
  spec = get_environment_spec("base")
  assert spec.id == "base"
  ids = {candidate.id for candidate in available_environments()}
  assert spec.id in ids


def test_get_environment_spec_unknown() -> None:
  with pytest.raises(KeyError):
    get_environment_spec("unknown")
