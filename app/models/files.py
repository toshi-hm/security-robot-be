from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class FileMetadata(Base):
  path: Mapped[str] = mapped_column(String(255))
  kind: Mapped[str] = mapped_column(String(50))
  content_type: Mapped[str] = mapped_column(String(100))
