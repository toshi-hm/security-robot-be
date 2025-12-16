import asyncio
import logging

from stable_baselines3.common.callbacks import CheckpointCallback

from app.core.redis_protocol import RedisPublisher
from app.core.training.ppo_service import PPOTrainingService
from app.db.session import SessionLocal
from app.models.training import TrainingJob

# from rl.callbacks.websocket_callback import DatabaseMetricsCallback # skipping for minimal debug

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class NoOpRedis(RedisPublisher):
  def publish(self, channel: str, message: str) -> None:
    pass


def main(args=None) -> None:
  session_id = 27
  db = SessionLocal()
  try:
    job = db.query(TrainingJob).filter(TrainingJob.id == session_id).first()
    if not job:
      print(f"Job {session_id} not found")
      return

    print(f"Found Job {session_id}: {job.name}, Status: {job.status}")

    config = job.config or {}
    # Ensure flat config has required fields
    config.update(
      {
        "total_timesteps": job.total_timesteps,
        "progress_update_interval": 250,
        "metrics_update_interval": 250,
        "coverage_weight": job.coverage_weight,
        "exploration_weight": job.exploration_weight,
        "diversity_weight": job.diversity_weight,
        "num_robots": job.num_robots,
        "env_width": job.env_width,
        "env_height": job.env_height,
      }
    )
    print("Config:", config)

    # Mock Redis
    redis_client = NoOpRedis()

    # Service
    service = PPOTrainingService()

    # We need rudimentary callbacks to avoid errors if logic depends on them
    callbacks: list[CheckpointCallback] = []
    if args and args.save_freq > 0:  # Added conditional check for args
      # Add a simple print callback?
      pass  # Placeholder for callback addition
    # The service.start_training expects callbacks list.

    print("Starting PPO Training via Service...")

    async def run() -> None:  # Added return type annotation
      result = await service.start_training(
        config=config,
        callbacks=callbacks,
        session_id=session_id,
        db_session_factory=SessionLocal,
        redis_publisher=redis_client,
      )
      print("Training Result:", result)

    asyncio.run(run())

  except Exception:
    logger.exception("Training Service Failed")
  finally:
    db.close()


if __name__ == "__main__":
  main()
