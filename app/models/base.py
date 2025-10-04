from datetime import datetime

from sqlalchemy.orm import DeclarativeBase, declared_attr, Mapped, mapped_column


class Base(DeclarativeBase):
  """Base class for all SQLAlchemy models."""

  id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
  created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
  updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

  @declared_attr.directive
  def __tablename__(cls) -> str:  # type: ignore[misc]
    return cls.__name__.lower()
