import logging
import pickle
import sys

from rl.environments.security_env import SecurityEnvironment

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_pickle():
  try:
    env = SecurityEnvironment(width=10, height=10)
    # Simulate set_logger which assigns a logger instance
    env.set_logger(logger)

    logger.info("Created environment")

    pickled = pickle.dumps(env)
    logger.info(f"Successfully pickled environment. Size: {len(pickled)} bytes")

    pickle.loads(pickled)
    logger.info("Successfully unpickled environment")

    return True
  except Exception as e:
    logger.error(f"Pickle failed: {e}")
    return False


if __name__ == "__main__":
  success = check_pickle()
  sys.exit(0 if success else 1)
