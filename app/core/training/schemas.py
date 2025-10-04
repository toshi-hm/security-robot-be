from pydantic import BaseModel


class TrainingConfig(BaseModel):
  algorithm: str
  environment_id: str
  total_timesteps: int


class TrainingSession(BaseModel):
  id: str
  status: str
