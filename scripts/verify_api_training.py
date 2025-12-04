import asyncio
import logging
from pathlib import Path
import sys
from unittest.mock import MagicMock

# Add project root to python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from app.core.training.ppo_service import ppo_service  # noqa: E402
from app.models.training import TrainingAlgorithm, TrainingJob  # noqa: E402
from app.services.training_service import TrainingService  # noqa: E402

# Configure logging
logging.basicConfig(
  level=logging.INFO,
  format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
  handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("verify_api")


async def run_verification() -> None:
  logger.info("Verifying API-triggered training configuration...")

  # Mock DB session
  mock_db = MagicMock()
  service = TrainingService(mock_db)

  # Create a mock job
  job = TrainingJob(
    id=999,
    name="Test Job",
    algorithm=TrainingAlgorithm.ppo,
    environment_type="enhanced",
    total_timesteps=1000,
    env_width=10,
    env_height=10,
    num_workers=1,
    num_robots=1,
    model_path="models/test_api_model.pth",
  )

  # Build config
  config = service.build_training_config(job)
  logger.info(f"Built config: {config}")

  if config.get("device") == "cuda":
    logger.info("SUCCESS: Device is set to 'cuda' in config.")
  else:
    logger.error(f"FAILURE: Device is set to '{config.get('device')}' in config.")
    return

  # Now verify actual training launch with this config
  logger.info("Starting training with built config...")
  try:
    result = await ppo_service.start_training(config=config)
    logger.info(f"Training result: {result}")

    if ppo_service.model:
      logger.info(f"Model device: {ppo_service.model.device}")
      logger.info(f"Model policy device: {next(ppo_service.model.policy.parameters()).device}")

  except Exception as e:
    logger.error(f"Training failed: {e}", exc_info=True)


if __name__ == "__main__":
  asyncio.run(run_verification())
