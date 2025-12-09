from unittest.mock import MagicMock, patch

import pytest

from app.core.training.ppo_service import PPOTrainingService


@pytest.fixture
def ppo_service():
  return PPOTrainingService(device="cpu")  # Force CPU for tests to avoid CUDA init


@pytest.mark.asyncio
async def test_start_training_parallel_envs(ppo_service):
  """Test starting training with parallel environments."""
  config = {
    "num_envs": 4,
    "policy_type": "MlpPolicy",
    "total_timesteps": 100,
    "env_width": 10,
    "env_height": 10,
    "environment_type": "standard",
    "batch_size": 2048,
  }

  with patch("app.core.training.ppo_service.SubprocVecEnv") as mock_vec_env_cls:
    # Mock the instance returned by SubprocVecEnv
    # Make sure it passes isinstance(env, VecEnv) check
    from stable_baselines3.common.vec_env import VecEnv

    mock_vec_env = MagicMock(spec=VecEnv)
    mock_vec_env_cls.return_value = mock_vec_env

    # Mock PPO to avoid actual training
    with patch("app.core.training.ppo_service.PPO") as mock_ppo_cls:
      mock_model = MagicMock()
      mock_ppo_cls.return_value = mock_model

      await ppo_service.start_training(config=config)

      # Verify SubprocVecEnv was initialized with correct number of functions
      assert mock_vec_env_cls.call_count == 1
      args, _ = mock_vec_env_cls.call_args
      env_fns = args[0]
      assert len(env_fns) == 4

      # Verify PPO initialized with correct policy and batch size
      mock_ppo_cls.assert_called_once()
      _, kwargs = mock_ppo_cls.call_args
      assert kwargs["policy"] == "MlpPolicy"
      assert kwargs["batch_size"] == 2048
      assert kwargs["env"] == mock_vec_env


@pytest.mark.asyncio
async def test_start_training_cnn_policy(ppo_service):
  """Test starting training with CNN policy."""
  config = {
    "num_envs": 1,
    "policy_type": "CnnPolicy",
    "total_timesteps": 100,
    "env_width": 10,
    "env_height": 10,
    "batch_size": 128,  # Custom batch size
  }

  with patch("app.core.training.ppo_service.DummyVecEnv") as mock_vec_env_cls:
    mock_vec_env = MagicMock()
    mock_vec_env_cls.return_value = mock_vec_env

    with patch("app.core.training.ppo_service.PPO") as mock_ppo_cls:
      mock_model = MagicMock()
      mock_ppo_cls.return_value = mock_model

      await ppo_service.start_training(config=config)

      # Verify PPO initialized with CnnPolicy
      _, kwargs = mock_ppo_cls.call_args
      assert kwargs["policy"] == "CnnPolicy"
      assert kwargs["batch_size"] == 128  # Should respect config override


@pytest.mark.asyncio
async def test_default_hyperparameters_gpu(ppo_service):
  """Test that default hyperparameters are adjusted for GPU/CNN."""
  config = {
    "num_envs": 1,
    "policy_type": "CnnPolicy",
    "total_timesteps": 100,
    # No batch_size or n_steps provided
  }

  with patch("app.core.training.ppo_service.DummyVecEnv"):
    with patch("app.core.training.ppo_service.PPO") as mock_ppo_cls:
      await ppo_service.start_training(config=config)

      _, kwargs = mock_ppo_cls.call_args
      # Should default to higher values for CNN
      assert kwargs["batch_size"] == 2048
      assert kwargs["n_steps"] == 4096
