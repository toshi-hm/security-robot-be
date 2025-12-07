import argparse
import asyncio
import json
import logging
from typing import Any

from redis import Redis
from sqlalchemy import text

from app.core.config import settings
from app.core.redis_protocol import RedisPublisher
from app.core.training.ppo_service import PPOTrainingService
from app.db.session import SessionLocal
from app.models.training import TrainingJobStatus
from rl.callbacks.redis_pubsub_callback import RedisTrainingCallback
from rl.callbacks.websocket_callback import DatabaseMetricsCallback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s'
)
logger = logging.getLogger(__name__)

class NoOpRedis(RedisPublisher):
    def publish(self, channel: str, message: str) -> None:
        pass

def _resolve_interval(value: Any, default: int) -> int:
    try:
        resolved = int(value)
    except (TypeError, ValueError):
        return default
    return resolved if resolved > 0 else default

async def process_job(job_id: int):
    logger.info(f"Processing Job {job_id} (Raw SQL mode)")
    db = SessionLocal()
    metrics_db = SessionLocal()
    try:
        # Fetch Job using Raw SQL to avoid Enum mapping issues
        result = db.execute(text("SELECT id, name, algorithm, config, total_timesteps, env_width, env_height, num_robots, coverage_weight, exploration_weight, diversity_weight FROM trainingjob WHERE id = :id"), {"id": job_id})
        row = result.mappings().one_or_none()

        if not row:
            logger.error(f"Job {job_id} not found in DB")
            return

        logger.info(f"Found Job {row['id']}: {row['name']}")

        # Update status to running (Raw SQL)
        db.execute(text("UPDATE trainingjob SET status = 'running', started_at = NOW() WHERE id = :id"), {"id": job_id})
        db.commit()

        # Build Config
        # Row keys map to columns. check capitalization? typically lowercase in postgres.
        # SQLAlchemy mappings() should be consistent with query.

        # Parse config (JSON)
        job_config = row['config']
        if isinstance(job_config, str):
            job_config = json.loads(job_config)
        elif job_config is None:
            job_config = {}

        config = job_config
        config.update({
            "total_timesteps": row['total_timesteps'],
            "progress_update_interval": 250,
            "metrics_update_interval": 250,
            "coverage_weight": row['coverage_weight'],
            "exploration_weight": row['exploration_weight'],
            "diversity_weight": row['diversity_weight'],
            "num_robots": row['num_robots'],
            "env_width": row['env_width'],
            "env_height": row['env_height'],
            "episode_log_file": f"/app/report/result/job_{job_id}_episodes.jsonl"
        })

        # Redis
        try:
            redis_client = Redis.from_url(settings.redis_url, decode_responses=False)
        except Exception:
            redis_client = NoOpRedis()

        # Callbacks
        progress_interval = _resolve_interval(config.get("progress_update_interval"), 250)
        metrics_interval = _resolve_interval(config.get("metrics_update_interval"), 250)

        def _status_probe():
            return TrainingJobStatus.running

        callbacks = [
            RedisTrainingCallback(
                session_id=job_id,
                redis_client=redis_client,
                update_interval=progress_interval,
                total_timesteps=config["total_timesteps"],
                state_hook=lambda meta: None, # print(f"Progress: {meta.get('progress', 0):.2f}"), # quiet
                status_getter=_status_probe,
                status_check_interval=progress_interval,
            ),
            DatabaseMetricsCallback(
                session_id=job_id,
                db_session=metrics_db,
                update_interval=metrics_interval,
            ),
        ]

        logger.info("Starting Service...")
        service = PPOTrainingService()
        result = await service.start_training(
            config=config,
            callbacks=callbacks,
            session_id=job_id,
            db_session_factory=SessionLocal,
            redis_publisher=redis_client
        )

        logger.info(f"Job {job_id} Finished: {result.get('status')}")

        # Mark completed (Raw SQL)
        status = result.get('status', 'failed')
        if status == 'completed':
            completion_status = 'completed'
        else:
            completion_status = 'failed'

        db.execute(text("UPDATE trainingjob SET status = :status, completed_at = NOW() WHERE id = :id"), {"status": completion_status, "id": job_id})
        db.commit()

    except Exception:
        logger.exception(f"Job {job_id} Failed")
        try:
             db.execute(text("UPDATE trainingjob SET status = 'failed', completed_at = NOW() WHERE id = :id"), {"id": job_id})
             db.commit()
        except:
             pass
    finally:
        db.close()
        metrics_db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", type=int, required=True)
    args = parser.parse_args()
    asyncio.run(process_job(args.job_id))
