from pydantic import BaseModel


class TrainingProgressEvent(BaseModel):
  session_id: str
  step: int
  reward: float
