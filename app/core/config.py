from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
  api_prefix: str = "/api/v1"
  allowed_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
  database_url: str = "sqlite+aiosqlite:///./security_robot.db"
  redis_url: str = "redis://localhost:6379/0"

  @field_validator('allowed_origins', mode='before')
  @classmethod
  def split_origins(cls, value: str | list[str]) -> list[str]:
    if isinstance(value, list):
      return value
    return [origin.strip() for origin in value.split(',') if origin.strip()]


settings = Settings()
