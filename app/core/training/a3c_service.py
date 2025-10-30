"""Service helpers for coordinating custom A3C training jobs."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Any

import torch
from sqlalchemy.orm import Session

from app.core.training.playback_recorder import wrap_environment_for_playback
from rl.algorithms.a3c.trainer import A3CTrainer
from rl.environments.enhanced_env import EnhancedSecurityEnvironment
from rl.environments.security_env import SecurityEnvironment

EnvironmentFactory = Callable[[], Any]


class A3CTrainingService:
  """High level orchestration entry point for the custom A3C trainer."""

  def __init__(self, *, device: str | torch.device = 'cpu') -> None:
    self._device = torch.device(device)

  def _create_environment(self, config: dict[str, Any]) -> Any:
    env_type = config.get('environment_type', 'standard')
    width = config.get('env_width', 8)
    height = config.get('env_height', 8)

    if env_type == 'standard':
      return SecurityEnvironment(width=width, height=height)
    if env_type == 'enhanced':
      return EnhancedSecurityEnvironment(
        width=width,
        height=height,
        coverage_weight=config.get('coverage_weight', 1.5),
        exploration_weight=config.get('exploration_weight', 3.0),
        diversity_weight=config.get('diversity_weight', 2.0),
      )
    raise ValueError(f"Unknown environment type: {env_type}")

  def _resolve_env_factory(
    self,
    config: dict[str, Any],
    *,
    session_id: int | None = None,
    session_factory: Callable[[], Session] | None = None,
    playback_options: dict[str, Any] | None = None,
  ) -> EnvironmentFactory:
    if 'env_factory' in config:
      factory = config['env_factory']
      if not callable(factory):
        raise ValueError('env_factory must be callable when provided')
      return factory
    base_factory = partial(self._create_environment, config)

    if session_id is not None and session_factory is not None:
      playback_config = dict(playback_options or {})
      playback_enabled = playback_config.pop('enabled', True)
      if playback_enabled:
        def _factory() -> Any:
          env = base_factory()
          return wrap_environment_for_playback(
            env,
            session_id=session_id,
            session_factory=session_factory,
            options=playback_config,
          )

        return _factory

    return base_factory

  async def start_training(
    self,
    *,
    config: dict[str, Any],
    progress_callback: Callable[[int, dict[str, Any]], None] | None = None,
    stop_signal: Callable[[], bool] | None = None,
    session_id: int | None = None,
    db_session_factory: Callable[[], Session] | None = None,
    playback_options: dict[str, Any] | None = None,
  ) -> dict[str, Any]:
    """Execute training asynchronously, delegating to a thread pool if needed."""

    config_copy = dict(config)
    playback_config = dict(config_copy.pop('playback', {}) or {})
    if playback_options:
      playback_config.update(playback_options)
    effective_session_id = session_id or config_copy.get('session_id')
    env_factory = self._resolve_env_factory(
      config_copy,
      session_id=int(effective_session_id) if effective_session_id is not None else None,
      session_factory=db_session_factory,
      playback_options=playback_config,
    )
    config_copy.pop('env_factory', None)

    loop = asyncio.get_running_loop()
    trainer = A3CTrainer(env_factory, config_copy, device=self._device)

    def _run_training() -> dict[str, Any]:
      return trainer.train(
        progress_callback=progress_callback,
        stop_signal=stop_signal,
      )

    return await loop.run_in_executor(None, _run_training)

  def save_model(self, model_state: dict[str, Any], path: str | Path) -> None:
    """Persist a trained model to disk."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    torch.save(model_state, destination)


a3c_service = A3CTrainingService()

