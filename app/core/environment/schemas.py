from pydantic import BaseModel


class EnvironmentDefinition(BaseModel):
  id: str
  name: str
  grid_rows: int
  grid_cols: int


class EnvironmentState(BaseModel):
  definition: EnvironmentDefinition
  robot_position: tuple[int, int]
