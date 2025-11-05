from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    api_prefix: str = "/api/v1"
    allowed_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    database_url: str = "sqlite+aiosqlite:///./security_robot.db"
    redis_url: str = "redis://localhost:6379/0"
    websocket_heartbeat_interval: float = 30.0
    environment_session_timeout_seconds: int = 1800
    max_a3c_workers: int = 16
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


settings = Settings()
