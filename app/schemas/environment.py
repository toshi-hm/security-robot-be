from pydantic import BaseModel

from app.core.environment.schemas import EnvironmentState


class EnvironmentStateResponse(BaseModel):
    data: EnvironmentState
