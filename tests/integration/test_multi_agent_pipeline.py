from pathlib import Path
import shutil
import tempfile
from unittest.mock import MagicMock

import pytest

from app.core.training.ppo_service import ppo_service


@pytest.mark.asyncio
async def test_multi_agent_training_pipeline():
  """
  Integration test for the multi-agent training pipeline.
  Verifies that the service can create a multi-agent environment,
  train a model, and save it.
  """
  # Create a temporary directory for outputs
  temp_dir = tempfile.mkdtemp()
  try:
    model_path = Path(temp_dir) / "test_model.zip"
    # log_path = Path(temp_dir) / "logs"

    # Configuration for multi-agent training
    config = {
      "environment_type": "standard",
      "env_width": 10,
      "env_height": 10,
      "num_robots": 2,  # Multi-agent configuration
      "total_timesteps": 200,  # Short run for testing
      "learning_rate": 0.0003,
      "batch_size": 64,
      "model_path": str(model_path),
      # "log_path": str(log_path), # Disable tensorboard logging
      "device": "cpu",  # Force CPU for testing
      "playback": {"enabled": False},  # Disable playback to avoid DB dependency
    }

    # Mock the database session factory since we don't need actual DB persistence for this test
    mock_db_session = MagicMock()

    # Run the training
    # We patch SessionLocal inside ppo_service if it was used directly,
    # but here we pass it as an argument or it's used in the pipeline script.
    # ppo_service.start_training uses db_session_factory only if playback is enabled.
    # We disabled playback, so it might not use it.
    # However, let's pass a mock just in case.

    result = await ppo_service.start_training(
      config=config, session_id=123, db_session_factory=mock_db_session
    )

    # Assertions
    assert result["status"] == "completed"
    assert result["algorithm"] == "ppo"
    assert Path(result["model_path"]).exists()

    from rl.environments.security_env import SecurityEnvironment

    # Verify environment state
    assert ppo_service.env is not None
    # Cast to SecurityEnvironment to satisfy mypy
    env = ppo_service.env
    assert isinstance(env, SecurityEnvironment)
    assert env.num_robots == 2
    assert len(env.robot_positions) == 2

    # Verify model was created
    assert ppo_service.model is not None

    # Verify action space dimension
    # MultiDiscrete([4, 4]) for 2 robots
    assert ppo_service.env.action_space.shape == (2,)
    # stable-baselines3 PPO handles MultiDiscrete

  finally:
    # Cleanup
    if ppo_service.env:
      ppo_service.env.close()
    shutil.rmtree(temp_dir)
