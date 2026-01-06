"""
Manual training script for single-agent experiment.
Runs PPO training directly in this process to ensure metrics are recorded and logs are visible.
"""

import asyncio
import logging
import os
import sys

# Ensure app is in path
sys.path.insert(0, os.getcwd())


from app.core.training.ppo_service import PPOTrainingService
from app.db.session import SessionLocal
from app.models.training import TrainingJob
from rl.callbacks.websocket_callback import DatabaseMetricsCallback

# Configure logging
logging.basicConfig(
  level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

SESSION_ID = 77


class MockRedis:
  def publish(self, channel, message):
    pass

  async def publish_message(self, channel, message):
    pass

  async def broadcast_to_session(self, session_id, message):
    pass


def main():
  db = SessionLocal()
  try:
    job = db.query(TrainingJob).filter(TrainingJob.id == SESSION_ID).first()
    if not job:
      print(f"Job {SESSION_ID} not found")
      return

    print(f"Starting Manual Training for Job {SESSION_ID}: {job.name}")

    # Reset job status
    job.status = "running"
    job.current_timestep = 0
    db.commit()

    config = job.config or {}
    # Ensure config has required fields for enhanced environment
    config.update(
      {
        "total_timesteps": 200000,
        "environment_type": "enhanced",  # MUST be enhanced
        "num_robots": 1,
        "env_width": 20,
        "env_height": 20,
        "enable_placement_learning": False,
        "verbose": 1,
      }
    )
    print(f"Config: {config}")

    service = PPOTrainingService()

    # Setup Callbacks
    callbacks = []

    # 1. Database Metrics (with our PPO fix)
    db_callback = DatabaseMetricsCallback(
      session_id=SESSION_ID,
      db_session=db,
      update_interval=500,  # Record every 500 steps
      verbose=1,
    )
    callbacks.append(db_callback)

    async def run():
      await service.start_training(
        config=config,
        callbacks=callbacks,
        session_id=SESSION_ID,
        db_session_factory=SessionLocal,
        redis_publisher=MockRedis(),
      )

    asyncio.run(run())
    print("Training Completed Successfully")

  except Exception:
    logger.exception("Training Failed")
  finally:
    db.close()


if __name__ == "__main__":
  main()
