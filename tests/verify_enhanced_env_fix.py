from pathlib import Path
import sys

# Add project root to python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from app.core.training.ppo_service import ppo_service
from rl.environments.enhanced_env import EnhancedSecurityEnvironment


def test_enhanced_env_num_robots():
  """Verify EnhancedSecurityEnvironment accepts num_robots."""
  env = EnhancedSecurityEnvironment(width=10, height=10, num_robots=3)
  assert env.num_robots == 3
  assert len(env.robot_positions) == 3
  print("EnhancedSecurityEnvironment correctly initialized with num_robots=3")


def test_ppo_service_creates_enhanced_env_with_robots():
  """Verify ppo_service passes num_robots to EnhancedSecurityEnvironment."""
  config = {
    "environment_type": "enhanced",
    "env_width": 10,
    "env_height": 10,
    "num_robots": 2,
  }
  env = ppo_service.create_environment(config)
  assert isinstance(env, EnhancedSecurityEnvironment)
  assert env.num_robots == 2
  print("ppo_service correctly created EnhancedSecurityEnvironment with num_robots=2")


if __name__ == "__main__":
  try:
    test_enhanced_env_num_robots()
    test_ppo_service_creates_enhanced_env_with_robots()
    print("All verification tests passed!")
  except AssertionError as e:
    print(f"Verification FAILED: {e}")
    sys.exit(1)
  except Exception as e:
    print(f"An error occurred: {e}")
    sys.exit(1)
