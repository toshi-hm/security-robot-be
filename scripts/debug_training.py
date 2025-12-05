import asyncio
import logging
from pathlib import Path
import sys

# Add project root to python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from app.core.training.ppo_service import ppo_service  # noqa: E402

# Configure logging
logging.basicConfig(
  level=logging.INFO,
  format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
  handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("debug_training")


async def run_debug_training():
  config = {
    "environment_type": "enhanced",
    "env_width": 10,
    "env_height": 10,
    "map_type": "random",
    "map_config": {"count": 5},
    "total_timesteps": 1000,  # Short run
    "num_workers": 1,
    "model_path": "models/debug_model.pth",
    "num_robots": 1,
    "device": "cuda",  # Explicitly request cuda
  }

  logger.info("Starting debug training...")
  try:
    # Mock DB session not needed for this debug as we don't provide session_id.
    # ppo_service handles None for db_session_factory in this case.

    result = await ppo_service.start_training(config=config)
    logger.info(f"Training result: {result}")

    if ppo_service.model:
      logger.info(f"Model device: {ppo_service.model.device}")
      logger.info(f"Model policy device: {next(ppo_service.model.policy.parameters()).device}")

  except Exception as e:
    logger.error(f"Training failed: {e}", exc_info=True)


if __name__ == "__main__":
  asyncio.run(run_debug_training())
