import asyncio
import logging
from pathlib import Path
import sys

# Add project root to python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from app.core.training.a3c_service import a3c_service
from app.db.session import SessionLocal
from app.models.training import TrainingAlgorithm, TrainingJob, TrainingJobStatus

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_pipeline")


async def run_verification():
  logger.info("Starting verification pipeline...")

  config = {
    "environment_type": "enhanced",
    "env_width": 10,
    "env_height": 10,
    "map_type": "maze",
    "total_timesteps": 100,  # Very short run
    "num_workers": 1,
    "playback": {"enabled": True, "record_interval": 1},
  }

  try:
    # Create job
    with SessionLocal() as session:
      job = TrainingJob(
        name="Verification Job",
        algorithm=TrainingAlgorithm.a3c,
        status=TrainingJobStatus.running,
        config=config,
      )
      session.add(job)
      session.commit()
      session.refresh(job)
      job_id = job.id
      logger.info(f"Created Job {job_id}")

    # Run training
    result = await a3c_service.start_training(
      config=config, session_id=job_id, db_session_factory=SessionLocal
    )

    logger.info(f"Training finished: {result}")

    # Verify playback data exists using sqlite3 directly to avoid threading issues
    import sqlite3

    conn = sqlite3.connect("security_robot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT count(*) FROM environmentstate WHERE session_id = ?", (job_id,))
    count = cursor.fetchone()[0]
    conn.close()

    logger.info(f"Recorded frames: {count}")
    if count > 0:
      print("Verification SUCCESS: Frames recorded.")
    else:
      print("Verification FAILED: No frames recorded.")
      sys.exit(1)

  except Exception as e:
    logger.error(f"Verification failed: {e}")
    sys.exit(1)


if __name__ == "__main__":
  asyncio.run(run_verification())
