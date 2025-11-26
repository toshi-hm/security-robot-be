from collections.abc import Callable
import logging
from pathlib import Path
from typing import Any

import gymnasium as gym
from sqlalchemy.orm import Session
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback, CallbackList
from stable_baselines3.common.vec_env import DummyVecEnv

from app.core.config import settings
from app.core.training.playback_recorder import wrap_environment_for_playback
from rl.callbacks.redis_pubsub_callback import TrainingCancelled

logger = logging.getLogger(__name__)


class PPOTrainingService:
  """Service for managing PPO training with Stable-Baselines3."""

  def __init__(self, device: str | None = None):
    """Initialize PPO training service.

    Args:
      device: Training device ('cpu', 'cuda', 'cuda:N', or None for auto-detection)
    """
    self.model: PPO | None = None
    self.env: gym.Env | None = None
    self._device = device if device is not None else settings.get_training_device()

  def create_environment(self, env_config: dict) -> gym.Env:
    """Create and configure the training environment.

    Args:
      env_config: Environment configuration including:
        - environment_type: 'standard' or 'enhanced'
        - env_width: Environment width
        - env_height: Environment height
        - Other environment-specific parameters

    Returns:
      Configured Gymnasium environment
    """
    env_type = env_config.get("environment_type", "standard")

    if env_type == "standard":
      from rl.environments.security_env import SecurityEnvironment

      env = SecurityEnvironment(
        width=env_config.get("env_width", 8), height=env_config.get("env_height", 8)
      )
    elif env_type == "enhanced":
      from rl.environments.enhanced_env import EnhancedSecurityEnvironment

      env = EnhancedSecurityEnvironment(
        width=env_config.get("env_width", 8),
        height=env_config.get("env_height", 8),
        coverage_weight=env_config.get("coverage_weight", 1.5),
        exploration_weight=env_config.get("exploration_weight", 3.0),
        diversity_weight=env_config.get("diversity_weight", 2.0),
      )
    else:
      raise ValueError(f"Unknown environment type: {env_type}")

    return env

  def create_model(
    self,
    env: gym.Env,
    learning_rate: float = 0.0003,
    batch_size: int = 64,
    n_steps: int = 2048,
    n_epochs: int = 10,
    gamma: float = 0.99,
    gae_lambda: float = 0.95,
    clip_range: float = 0.2,
    verbose: int = 1,
    tensorboard_log: str | None = None,
    device: str | None = None,
  ) -> PPO:
    """Create PPO model with specified hyperparameters.

    Args:
      env: Training environment
      learning_rate: Learning rate
      batch_size: Batch size for training
      n_steps: Number of steps to run for each environment per update
      n_epochs: Number of epochs when optimizing the surrogate loss
      gamma: Discount factor
      gae_lambda: Factor for trade-off of bias vs variance for GAE
      clip_range: Clipping parameter for PPO
      verbose: Verbosity level
      tensorboard_log: Path for TensorBoard logs
      device: Training device (overrides instance device if provided)

    Returns:
      Configured PPO model
    """
    # Wrap environment in DummyVecEnv for Stable-Baselines3
    vec_env = DummyVecEnv([lambda: env])

    # Use provided device or fall back to instance device
    effective_device = device if device is not None else self._device
    logger.info(f"Creating PPO model on device: {effective_device}")

    model = PPO(
      policy="MlpPolicy",
      env=vec_env,
      learning_rate=learning_rate,
      n_steps=n_steps,
      batch_size=batch_size,
      n_epochs=n_epochs,
      gamma=gamma,
      gae_lambda=gae_lambda,
      clip_range=clip_range,
      verbose=verbose,
      tensorboard_log=tensorboard_log,
      device=effective_device,
    )

    return model

  async def start_training(
    self,
    *,
    config: dict,
    callbacks: list[BaseCallback] | None = None,
    progress_callback: Callable | None = None,
    session_id: int | None = None,
    db_session_factory: Callable[[], Session] | None = None,
    playback_options: dict[str, Any] | None = None,
  ) -> dict:
    """Start PPO training with the given configuration.

    Args:
      config: Training configuration including:
        - total_timesteps: Total training timesteps
        - learning_rate: Learning rate
        - batch_size: Batch size
        - env_width, env_height: Environment dimensions
        - environment_type: 'standard' or 'enhanced'
        - model_path: Path to save the trained model
        - log_path: Path for TensorBoard logs
      callbacks: List of Stable-Baselines3 callbacks
      progress_callback: Optional async callback for progress updates

    Returns:
      Training result dictionary
    """
    try:
      # Create environment
      environment = self.create_environment(config)

      effective_session_id = session_id or config.get("session_id")
      playback_config = dict(config.get("playback") or {})
      if playback_options:
        playback_config.update(playback_options)
      playback_enabled = playback_config.pop("enabled", True)

      if effective_session_id is not None and db_session_factory is not None and playback_enabled:
        environment = wrap_environment_for_playback(
          environment,
          session_id=int(effective_session_id),
          session_factory=db_session_factory,
          options=playback_config,
        )

      self.env = environment

      # Prepare log directory
      log_path = config.get("log_path")
      if log_path:
        Path(log_path).mkdir(parents=True, exist_ok=True)

      # Create model
      # Allow config to override device
      device = config.get("device", self._device)
      self.model = self.create_model(
        env=self.env,
        learning_rate=config.get("learning_rate", 0.0003),
        batch_size=config.get("batch_size", 64),
        verbose=1,
        tensorboard_log=log_path,
        device=device,
      )

      # Setup callbacks
      callback_list = CallbackList(callbacks) if callbacks else None

      # Start training
      total_timesteps = config.get("total_timesteps", 50000)
      logger.info(f"Starting PPO training for {total_timesteps} timesteps")

      self.model.learn(total_timesteps=total_timesteps, callback=callback_list, progress_bar=True)

      # Save model
      model_path = config.get("model_path")
      if model_path:
        Path(model_path).parent.mkdir(parents=True, exist_ok=True)
        self.model.save(model_path)
        logger.info(f"Model saved to {model_path}")

      return {
        "status": "completed",
        "algorithm": "ppo",
        "total_timesteps": total_timesteps,
        "model_path": model_path,
      }

    except TrainingCancelled as exc:
      logger.info("PPO training cancelled: %s", exc)
      return {
        "status": "paused",
        "algorithm": "ppo",
        "total_timesteps": getattr(self.model, "num_timesteps", 0),
      }
    except Exception as e:
      logger.error(f"PPO training failed: {e}", exc_info=True)
      return {"status": "failed", "algorithm": "ppo", "error": str(e)}

    finally:
      # Cleanup
      if self.env:
        self.env.close()

  def load_model(
    self, model_path: str, env: gym.Env | None = None, device: str | None = None
  ) -> PPO:
    """Load a trained PPO model from disk.

    Args:
      model_path: Path to the saved model
      env: Optional environment (will create DummyVecEnv if provided)
      device: Device to load model on (overrides instance device if provided)

    Returns:
      Loaded PPO model
    """
    effective_device = device if device is not None else self._device
    logger.info(f"Loading PPO model from {model_path} on device: {effective_device}")

    if env:
      vec_env = DummyVecEnv([lambda: env])
      model = PPO.load(model_path, env=vec_env, device=effective_device)
    else:
      model = PPO.load(model_path, device=effective_device)

    self.model = model
    return model

  def stop_training(self) -> None:
    """Stop the current training session."""
    # Note: Stable-Baselines3 doesn't provide built-in stop mechanism
    # This would need to be implemented via a custom callback
    logger.warning("PPO training stop requested - implement via callback")


# Singleton instance
ppo_service = PPOTrainingService()
