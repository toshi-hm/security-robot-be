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
logger = logging.getLogger("run_cycle_12")


async def run_cycle_12():
  # Cycle 12 Parameters
  # Dynamic Patrol Radius is enabled in SecurityEnvironment code (threshold based)
  config = {
    "environment_type": "enhanced",
    "env_width": 20,
    "env_height": 20,
    "map_type": "random",
    "map_config": {"seed": 42},
    "total_timesteps": 100000,
    "num_workers": 1,
    "model_path": "models/cycle_12_efficiency.pth",
    "num_robots": 3,
    "device": "auto",
    # Reward Weights (Same as C11 to isolate efficiency gain)
    "coverage_weight": 1.0,
    "exploration_weight": 0.5,
    "diversity_weight": 0.5,
    "threat_penalty_weight": 50.0,
    # Battery
    "battery_drain_rate": 0.001,
    # Logging
    "episode_log_file": str(project_root / "report/result/job_48_episodes.jsonl"),
    "strategic_init_mode": False,
  }

  logger.info("Starting Cycle 12 (Dynamic Patrol Radius) training...")
  logger.info(f"Config: {config}")

  try:
    # Run without DB session factory (standalone mode)
    result = await ppo_service.start_training(config=config)
    logger.info(f"Training result: {result}")

  except Exception as e:
    logger.error(f"Training failed: {e}", exc_info=True)


if __name__ == "__main__":
  asyncio.run(run_cycle_12())
