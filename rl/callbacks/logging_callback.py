from app.utils.logging import logger


def log_training_progress(step: int, reward: float) -> None:
  logger.info('Step %s reward %s', step, reward)
