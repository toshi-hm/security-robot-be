from collections.abc import Callable
import logging
from pathlib import Path
from typing import Any

import gymnasium as gym
from sqlalchemy.orm import Session
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback, CallbackList
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv, VecEnv

from app.core.config import settings
from app.core.redis_protocol import RedisPublisher
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
    self.env: gym.Env | VecEnv | None = None
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
    print(f"DEBUG: create_environment called with env_type={env_type}")
    print(f"DEBUG: episode_log_file={env_config.get('episode_log_file')}")
    print(f"DEBUG: threat_penalty_weight={env_config.get('threat_penalty_weight')}")

    if env_type == "standard":
      from rl.environments.security_env import SecurityEnvironment

      env = SecurityEnvironment(
        width=env_config.get("env_width", 8),
        height=env_config.get("env_height", 8),
        num_robots=env_config.get("num_robots", 1),
      )
    elif env_type == "enhanced":
      from rl.environments.enhanced_env import EnhancedSecurityEnvironment

      env = EnhancedSecurityEnvironment(
        width=env_config.get("env_width", 8),
        height=env_config.get("env_height", 8),
        num_robots=env_config.get("num_robots", 1),
        coverage_weight=env_config.get("coverage_weight", 1.5),
        exploration_weight=env_config.get("exploration_weight", 3.0),
        diversity_weight=env_config.get("diversity_weight", 2.0),
        threat_penalty_weight=env_config.get("threat_penalty_weight", 0.0),
        battery_drain_rate=env_config.get("battery_drain_rate", 0.001),
        episode_log_file=env_config.get("episode_log_file"),
        strategic_init_mode=env_config.get("strategic_init_mode", False),
      )
    else:
      raise ValueError(f"Unknown environment type: {env_type}")

    return env

  def create_model(
    self,
    env: gym.Env | VecEnv,
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
    policy_type: str = "MlpPolicy",
  ) -> PPO:
    """Create PPO model with specified hyperparameters.

    Args:
      env: Training environment (gym.Env or VecEnv)
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
      policy_type: Policy network type ("MlpPolicy" or "CnnPolicy")

    Returns:
      Configured PPO model
    """
    # Wrap environment in DummyVecEnv if it's a standard gym.Env
    if isinstance(env, VecEnv):
      vec_env = env
    else:
      vec_env = DummyVecEnv([lambda: env])

    # Use provided device or fall back to instance device
    effective_device = device if device is not None else self._device
    logger.info(f"Creating PPO model with {policy_type} on device: {effective_device}")

    model = PPO(
      policy=policy_type,
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
    redis_publisher: RedisPublisher | None = None,
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
      # Create environment(s)
      num_envs = config.get("num_envs", 1)
      environment_config = config
      # Only enable playback for the first environment if parallel
      playback_config = dict(config.get("playback") or {})
      if playback_options:
        playback_config.update(playback_options)
      playback_enabled = playback_config.pop("enabled", True)
      effective_session_id = session_id or config.get("session_id")

      # Playback is enabled for parallel execution (handled by rank check in make_env)
      if num_envs > 1 and playback_enabled:
        logger.info(
          "Parallel training (num_envs > 1): Playback recording will be active on rank 0 only."
        )

      should_wrap_playback = (
        effective_session_id is not None and db_session_factory is not None and playback_enabled
      )

      def make_env(rank: int) -> Callable[[], gym.Env]:
        def _init() -> gym.Env:
          env = self.create_environment(environment_config)
          # Only wrap rank 0 for playback to avoid database contention and confused logs
          if rank == 0 and should_wrap_playback:
            return wrap_environment_for_playback(
              env,
              session_id=int(effective_session_id),  # type: ignore
              session_factory=db_session_factory,  # type: ignore
              options=playback_config,
              redis_publisher=redis_publisher,
            )
          return env

        return _init

      if num_envs > 1:
        logger.info(f"Creating {num_envs} parallel environments (SubprocVecEnv)")
        # Use SubprocVecEnv for parallel execution
        # We manually create list of constructors to handle conditional wrapping
        env_fns = [make_env(i) for i in range(num_envs)]
        self.env = SubprocVecEnv(env_fns)
      else:
        logger.info("Creating single environment (DummyVecEnv)")
        self.env = DummyVecEnv([make_env(0)])

      # Prepare log directory
      log_path = config.get("log_path")
      if log_path:
        Path(log_path).mkdir(parents=True, exist_ok=True)

      # Create model
      # Allow config to override device
      device = config.get("device", self._device)
      policy_type = config.get("policy_type", "MlpPolicy")

      # Adjust default hyperparameters for better GPU utilization if not specified
      default_batch_size = 2048 if policy_type == "CnnPolicy" or num_envs > 1 else 64
      default_n_steps = 4096 if policy_type == "CnnPolicy" or num_envs > 1 else 2048

      actual_batch_size = config.get("batch_size", default_batch_size)
      actual_n_steps = config.get("n_steps", default_n_steps)

      if num_envs > 1 or policy_type == "CnnPolicy":
        logger.info(
          f"Auto-tuning hyperparameters for efficient parallel/GPU training: "
          f"batch_size={actual_batch_size}, n_steps={actual_n_steps}"
        )

      self.model = self.create_model(
        env=self.env,
        learning_rate=config.get("learning_rate", 0.0003),
        batch_size=actual_batch_size,
        n_steps=actual_n_steps,
        verbose=1,
        tensorboard_log=log_path,
        device=device,
        policy_type=policy_type,
      )

      # Setup callbacks
      callback_list = CallbackList(callbacks) if callbacks else None

      # Start training
      total_timesteps = config.get("total_timesteps", 50000)
      logger.info(f"Starting PPO training for {total_timesteps} timesteps")

      # Log the actual device of the model parameters
      if self.model:
        device = self.model.device
        logger.info(f"Model is on device: {device}")
        # Also check a parameter to be sure
        try:
          param_device = next(self.model.policy.parameters()).device
          logger.info(f"Model policy parameters are on device: {param_device}")
        except StopIteration:
          logger.warning("Model has no parameters to check device.")

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
