from pydantic import BaseModel

from app.models.training import TrainingAlgorithm


class TrainingConfig(BaseModel):
  algorithm: TrainingAlgorithm
  environment_id: str
  total_timesteps: int
  num_robots: int = 1


class TrainingSession(BaseModel):
  id: str
  status: str
