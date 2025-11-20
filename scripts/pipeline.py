"""Automated training pipeline for security robot."""

import asyncio
import logging
from pathlib import Path
import sys

# Add project root to python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from app.core.training.a3c_service import a3c_service  # noqa: E402

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("pipeline")

async def run_pipeline():
    stages = [
        {
            "name": "Stage 1: Small Random",
            "config": {
                "environment_type": "enhanced",
                "env_width": 10,
                "env_height": 10,
                "map_type": "random",
                "map_config": {"obstacle_count": 5},
                "total_timesteps": 5000,
                "num_workers": 4,
                "model_path": "models/stage1_random.pth"
            }
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
                "model_path": "models/stage2_maze.pth"
            }
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
                "model_path": "models/stage3_room.pth"
            }
        }
    ]

    # Note: Stages are executed sequentially to allow for potential transfer learning
    # where later stages could load weights from earlier stages.
    for stage in stages:
        logger.info(f"Starting {stage['name']}")
        logger.info(f"Configuration: {stage['config']}")

        # Security check: Prevent path traversal in model_path
        model_path_str = stage['config'].get('model_path')
        if model_path_str:
            try:
                # Resolve path relative to project root
                safe_path = (project_root / model_path_str).resolve()
                # Check if the resolved path is within the project root
                safe_path.relative_to(project_root.resolve())
            except (ValueError, OSError) as e:
                logger.error(f"Invalid model_path in {stage['name']}: {e}")
                continue  # Skip this stage


        try:
            result = await a3c_service.start_training(config=stage['config'])
            logger.info(f"Finished {stage['name']}")
            logger.info(f"Result: {result}")

            # Optional: Load the model from the previous stage to continue training?
            # For now, we start fresh or rely on the fact that we might want to
            # transfer weights later.
            # To transfer weights, we would need to load the state dict.

        except Exception as e:
            logger.error(f"Failed {stage['name']}: {e}")
            # Decide whether to continue or stop
            # break

if __name__ == "__main__":
    asyncio.run(run_pipeline())
