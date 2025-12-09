import logging
import sys

import numpy as np

from rl.environments.enhanced_env import EnhancedSecurityEnvironment

# Config logging to stderr
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger(__name__)


def test_logging() -> None:
  print("Initializing Env...")
  env = EnhancedSecurityEnvironment(
    battery_drain_rate=0.1,  # fast drain
    num_robots=1,
    episode_log_file="/app/report/result/test_log.jsonl",
  )

  print("Reset 1")
  env.reset()

  print("Stepping 1100 times...")
  for i in range(1100):
    # Action 0: Move
    # Action needs to be numpy array for vectorized env compatibility (standard check)
    # Even though we are using single env directly here without wrapper.
    # But EnhancedEnv expects list logic internal?
    # Mypy says expected ndarray.
    obs, rewards, terminated, truncated, infos = env.step(np.array([0] * 1))
    if terminated or truncated:
      print(f"Terminated at step {i + 1}")
      break


if __name__ == "__main__":
  logging.basicConfig(level=logging.DEBUG)
  test_logging()
