from pydantic import BaseModel


class TrainingRequest(BaseModel):
  name: str
  algorithm: str
  environment_type: str
  total_timesteps: int


class TrainingMetricsResponse(BaseModel):
  session_id: str
  points: list[dict[str, float]]
