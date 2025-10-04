from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class EnvironmentDefinition(Base):
  name: Mapped[str] = mapped_column(String(100))
  description: Mapped[str] = mapped_column(String(255), default='')
  config: Mapped[dict] = mapped_column(JSON, default=dict)
