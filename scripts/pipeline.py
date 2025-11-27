"""Automated training pipeline for security robot."""

import asyncio
import logging
from pathlib import Path
import sys
from typing import Any, NotRequired, TypedDict

# Add project root to python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from app.core.training.ppo_service import ppo_service  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.training import TrainingAlgorithm, TrainingJob, TrainingJobStatus  # noqa: E402

# Configure logging
logging.basicConfig(
  level=logging.INFO,
  format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
  handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("pipeline")


class StageConfig(TypedDict):
  environment_type: str
  env_width: int
  env_height: int
  map_type: str
  total_timesteps: int
  num_workers: int
  model_path: str
  map_config: NotRequired[dict[str, int]]


class Stage(TypedDict):
  name: str
  config: StageConfig
  critical: NotRequired[bool]


async def run_pipeline() -> None:
  stages: list[Stage] = [
    {
      "name": "Stage 1: Small Random",
      "config": {
        "environment_type": "enhanced",
        "env_width": 10,
        "env_height": 10,
        "map_type": "random",
        "map_config": {"count": 5},
        "total_timesteps": 5000,
        "num_workers": 4,
        "model_path": "models/stage1_random.pth",
      },
      "critical": True,  # Critical stage - must succeed
    },
    {
      "name": "Stage 2: Medium Maze",
      "config": {
        "environment_type": "enhanced",
        "env_width": 15,
        "env_height": 15,
        "map_type": "maze",
        "total_timesteps": 10000,
        "num_workers": 4,
        "model_path": "models/stage2_maze.pth",
      },
    },
    {
      "name": "Stage 3: Large Room",
      "config": {
        "environment_type": "enhanced",
        "env_width": 20,
        "env_height": 20,
        "map_type": "room",
        "total_timesteps": 15000,
        "num_workers": 4,
        "model_path": "models/stage3_room.pth",
      },
    },
  ]

  # Note: Stages are executed sequentially to allow for potential transfer learning
  # where later stages could load weights from earlier stages.
  for stage in stages:
    logger.info(f"Starting {stage['name']}")
    logger.info(f"Configuration: {stage['config']}")

    # Security check: Prevent path traversal in model_path
    model_path_str = stage["config"].get("model_path")
    if model_path_str:
      try:
        # Resolve path relative to project root
        safe_path = (project_root / model_path_str).resolve()
        # Check if the resolved path is within the project root
        safe_path.relative_to(project_root.resolve())
      except ValueError as e:
        # Path traversal attempt detected
        logger.error(
          f"Security: Path traversal attempt detected in {stage['name']}: {model_path_str}"
        )
        logger.debug(f"Details: {e}")
        continue  # Skip this stage
      except OSError as e:
        # Filesystem error
        logger.error(f"Filesystem error in {stage['name']}: {e}")
        continue  # Skip this stage

    try:
      # Create a training job record for this stage
      with SessionLocal() as session:
        job = TrainingJob(
          name=f"Pipeline: {stage['name']}",
          algorithm=TrainingAlgorithm.ppo,
          status=TrainingJobStatus.running,
          environment_type=stage["config"].get("environment_type", "standard"),
          env_width=stage["config"].get("env_width", 8),
          env_height=stage["config"].get("env_height", 8),
          total_timesteps=stage["config"].get("total_timesteps", 0),
          config=stage["config"],
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        job_id = job.id
        logger.info(f"Created TrainingJob {job_id} for {stage['name']}")

      # Enable playback for this stage
      stage_config: dict[str, Any] = dict(stage["config"])
      stage_config["playback"] = {"enabled": True, "record_interval": 1}

      result = await ppo_service.start_training(
        config=stage_config, session_id=job_id, db_session_factory=SessionLocal
      )

      # Update job status on completion
      with SessionLocal() as session:
        job_record = session.get(TrainingJob, job_id)
        if job_record:
          job_record.status = TrainingJobStatus.completed
          job_record.model_path = str(result.get("model_path", ""))
          session.commit()

      logger.info(f"Finished {stage['name']}")
      logger.info(f"Result: {result}")

      # Optional: Load the model from the previous stage to continue training?
      # For now, we start fresh or rely on the fact that we might want to
      # transfer weights later.
      # To transfer weights, we would need to load the state dict.

    except Exception as e:
      logger.error(f"Failed {stage['name']}: {e}")

      # Resource Cleanup: Delete potential partial model file
      model_path_str = stage["config"].get("model_path")
      if model_path_str:
        try:
          model_path = (project_root / model_path_str).resolve()
          if model_path.exists() and model_path.is_file():
            logger.warning(f"Cleaning up incomplete model file: {model_path}")
            model_path.unlink()
        except Exception as cleanup_error:
          logger.error(f"Failed to cleanup model file: {cleanup_error}")

      # Check if this is a critical stage
      if stage.get("critical", False):
        logger.error("Critical stage failed. Stopping pipeline.")
        break
      # Otherwise continue to next stage


if __name__ == "__main__":
  asyncio.run(run_pipeline())
