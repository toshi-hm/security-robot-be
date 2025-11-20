import logging

from pydantic import field_validator
from pydantic_settings import BaseSettings
import torch

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
  api_prefix: str = "/api/v1"
  allowed_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
  database_url: str = "sqlite+aiosqlite:///./security_robot.db"
  redis_url: str = "redis://localhost:6379/0"
  websocket_heartbeat_interval: float = 30.0
  environment_session_timeout_seconds: int = 1800
  max_a3c_workers: int = 16
  training_device: str = "auto"
  playback_archive_chunk_size: int = 1000
  playback_archive_delete_batch_size: int = 1000
  playback_archive_max_bytes: int = (
    524_288_000  # 500 MiB default chosen to fit under typical object storage limits
  )
  playback_archive_max_expansion_ratio: int = (
    10  # Guard against archives expanding beyond 10x the compressed size
  )

  @field_validator("allowed_origins", mode="before")
  @classmethod
  def split_origins(cls, value: str | list[str]) -> list[str]:
    if isinstance(value, list):
      return value
    return [origin.strip() for origin in value.split(",") if origin.strip()]

  @field_validator("max_a3c_workers")
  @classmethod
  def validate_max_a3c_workers(cls, value: int) -> int:
    if value < 1:
      raise ValueError("max_a3c_workers must be a positive integer")
    return value

  @field_validator("playback_archive_chunk_size")
  @classmethod
  def validate_playback_archive_chunk_size(cls, value: int) -> int:
    if value < 1:
      raise ValueError("playback_archive_chunk_size must be a positive integer")
    return value

  @field_validator("playback_archive_delete_batch_size")
  @classmethod
  def validate_playback_archive_delete_batch_size(cls, value: int) -> int:
    if value < 1:
      raise ValueError("playback_archive_delete_batch_size must be a positive integer")
    return value

  @field_validator("playback_archive_max_bytes")
  @classmethod
  def validate_playback_archive_max_bytes(cls, value: int) -> int:
    if value < 1:
      raise ValueError("playback_archive_max_bytes must be a positive integer")
    return value

  @field_validator("playback_archive_max_expansion_ratio")
  @classmethod
  def validate_playback_archive_max_expansion_ratio(cls, value: int) -> int:
    if value < 1:
      raise ValueError("playback_archive_max_expansion_ratio must be a positive integer")
    return value

  @field_validator("training_device")
  @classmethod
  def validate_training_device(cls, value: str) -> str:
    """Validate and normalize training device specification.

    Accepts:
    - "auto": automatically select CUDA if available, else CPU
    - "cpu": force CPU usage
    - "cuda": use default CUDA device
    - "cuda:N": use specific CUDA device N
    """
    value = value.strip().lower()
    if value not in ("auto", "cpu") and not value.startswith("cuda"):
      raise ValueError(
        "training_device must be 'auto', 'cpu', 'cuda', or 'cuda:N' (e.g., 'cuda:0')"
      )
    # Validate CUDA device availability if explicitly requested
    if value.startswith("cuda"):
      if not torch.cuda.is_available():
        raise ValueError(f"CUDA device '{value}' requested but CUDA is not available")
      # Check specific device index if provided
      if ":" in value:
        try:
          device_idx = int(value.split(":")[1])
          if device_idx >= torch.cuda.device_count():
            raise ValueError(
              f"CUDA device index {device_idx} out of range "
              f"(available: 0-{torch.cuda.device_count() - 1})"
            )
        except (ValueError, IndexError) as e:
          raise ValueError(f"Invalid CUDA device specification '{value}'") from e
    return value

  def get_training_device(self) -> str:
    """Resolve the training device based on current settings.

    Returns:
      Device string suitable for PyTorch/Stable-Baselines3 ('cpu', 'cuda', or 'cuda:N')
    """
    if self.training_device == "auto":
      device = "cuda" if torch.cuda.is_available() else "cpu"
      logger.info(f"Auto-detected training device: {device}")
      return device
    logger.info(f"Using configured training device: {self.training_device}")
    return self.training_device


settings = Settings()
