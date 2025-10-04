from pydantic import BaseModel


class EnvironmentStateResponse(BaseModel):
  environment_id: str
  grid: list[list[int]]
