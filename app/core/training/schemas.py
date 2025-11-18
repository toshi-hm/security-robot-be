from pydantic import BaseModel

from app.models.training import TrainingAlgorithm


class TrainingConfig(BaseModel):
  algorithm: TrainingAlgorithm
  environment_id: str
  total_timesteps: int


class TrainingSession(BaseModel):
  id: str
  status: str
