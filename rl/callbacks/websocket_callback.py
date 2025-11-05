"""WebSocket callback for streaming training progress."""

import asyncio
import logging

import numpy as np
from stable_baselines3.common.callbacks import BaseCallback

from app.utils.datetime import utcnow

logger = logging.getLogger(__name__)


class WebSocketTrainingCallback(BaseCallback):
    """
    Stable-Baselines3 callback that streams training progress via WebSocket.

    This callback sends training metrics to connected WebSocket clients at regular intervals.
    """

    def __init__(
        self, session_id: int, websocket_manager, update_interval: int = 100, verbose: int = 0
    ):
        """
        Initialize WebSocket callback.

        Args:
          session_id: Training session ID
          websocket_manager: WebSocket manager instance
          update_interval: Send updates every N timesteps
          verbose: Verbosity level
        """
        super().__init__(verbose)
        self.session_id = session_id
        self.websocket_manager = websocket_manager
        self.update_interval = update_interval
        self.episode_rewards = []
        self.episode_lengths = []
        self.current_episode_reward = 0
        self.current_episode_length = 0

    def _on_training_start(self) -> None:
        """Called before the first rollout."""
        self._send_status_update("running", "Training started")

    def _on_rollout_start(self) -> None:
        """Called before collecting new samples."""
        pass

    def _on_step(self) -> bool:
        """
        Called after each environment step.

        Returns:
          If False, training will be stopped.
        """
        # Track episode progress
        self.current_episode_reward += self.locals.get("rewards", [0])[0]
        self.current_episode_length += 1

        # Check if episode ended
        done = self.locals.get("dones", [False])[0]
        if done:
            self.episode_rewards.append(self.current_episode_reward)
            self.episode_lengths.append(self.current_episode_length)
            self.current_episode_reward = 0
            self.current_episode_length = 0

        # Send progress update at intervals
        if self.n_calls % self.update_interval == 0:
            self._send_progress_update()

        return True  # Continue training

    def _on_rollout_end(self) -> None:
        """Called after rollout collection."""
        pass

    def _on_training_end(self) -> None:
        """Called at the end of training."""
        self._send_status_update("completed", "Training completed successfully")

    def _send_progress_update(self) -> None:
        """Send training progress update via WebSocket."""
        try:
            # Calculate metrics
            mean_reward = (
                float(np.mean(self.episode_rewards[-10:])) if self.episode_rewards else 0.0
            )

            # Get loss from logger if available
            loss = None
            if hasattr(self.model, "logger") and self.model.logger:
                loss_key = "train/loss"
                if loss_key in self.model.logger.name_to_value:
                    loss = float(self.model.logger.name_to_value[loss_key])

            message = {
                "type": "training_progress",
                "session_id": self.session_id,
                "timestep": self.num_timesteps,
                "episode": len(self.episode_rewards),
                "reward": mean_reward,
                "loss": loss,
                "additional_metrics": {
                    "episode_length": int(np.mean(self.episode_lengths[-10:]))
                    if self.episode_lengths
                    else 0,
                    "total_episodes": len(self.episode_rewards),
                },
            }

            # Send via WebSocket (async operation)
            asyncio.create_task(
                self.websocket_manager.broadcast_to_session(self.session_id, message)
            )

            if self.verbose > 0:
                logger.info(
                    f"Sent progress update: timestep={self.num_timesteps}, reward={mean_reward:.2f}"
                )

        except Exception as e:
            logger.error(f"Failed to send WebSocket update: {e}")

    def _send_status_update(self, status: str, message: str) -> None:
        """Send training status update via WebSocket."""
        try:
            status_message = {
                "type": "training_status",
                "session_id": self.session_id,
                "status": status,
                "message": message,
            }

            asyncio.create_task(
                self.websocket_manager.broadcast_to_session(self.session_id, status_message)
            )

            if self.verbose > 0:
                logger.info(f"Sent status update: {status} - {message}")

        except Exception as e:
            logger.error(f"Failed to send status update: {e}")


class DatabaseMetricsCallback(BaseCallback):
    """
    Callback that saves training metrics to the database.
    """

    def __init__(self, session_id: int, db_session, update_interval: int = 100, verbose: int = 0):
        """
        Initialize database metrics callback.

        Args:
          session_id: Training session ID
          db_session: SQLAlchemy database session
          update_interval: Save metrics every N timesteps
          verbose: Verbosity level
        """
        super().__init__(verbose)
        self.session_id = session_id
        self.db_session = db_session
        self.update_interval = update_interval
        self.episode_rewards = []
        self.current_episode_reward = 0

    def _on_step(self) -> bool:
        """Save metrics to database at intervals."""
        # Track episode reward
        self.current_episode_reward += self.locals.get("rewards", [0])[0]

        done = self.locals.get("dones", [False])[0]
        if done:
            self.episode_rewards.append(self.current_episode_reward)
            self.current_episode_reward = 0

        # Save to database at intervals
        if self.n_calls % self.update_interval == 0:
            self._save_metrics()

        return True

    def _save_metrics(self) -> None:
        """Save current metrics to database."""
        try:
            from app.models.training import TrainingMetric

            mean_reward = (
                float(np.mean(self.episode_rewards[-10:])) if self.episode_rewards else 0.0
            )

            # Get loss if available
            loss = None
            if hasattr(self.model, "logger") and self.model.logger:
                loss_key = "train/loss"
                if loss_key in self.model.logger.name_to_value:
                    loss = float(self.model.logger.name_to_value[loss_key])

            metric = TrainingMetric(
                job_id=self.session_id,
                timestep=self.num_timesteps,
                episode=len(self.episode_rewards),
                reward=mean_reward,
                loss=loss,
                timestamp=utcnow(),
            )

            self.db_session.add(metric)
            self.db_session.commit()

            if self.verbose > 0:
                logger.info(f"Saved metrics to database: timestep={self.num_timesteps}")

        except Exception as e:
            logger.error(f"Failed to save metrics to database: {e}")
            self.db_session.rollback()


# Legacy function for backward compatibility
def emit_training_progress(step: int, reward: float) -> None:
    """Legacy function - use WebSocketTrainingCallback instead."""
    logger.warning("emit_training_progress is deprecated, use WebSocketTrainingCallback")
