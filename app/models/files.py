
from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class FileMetadata(Base):
  """Metadata for uploaded files (models, logs, etc.)."""

  # File information
  filename: Mapped[str] = mapped_column(String(255))
  original_filename: Mapped[str] = mapped_column(String(255))
  file_path: Mapped[str] = mapped_column(String(512))
  file_size: Mapped[int] = mapped_column()  # Size in bytes

  # File type
  file_type: Mapped[str] = mapped_column(String(50))  # 'model', 'log', 'config', etc.
  content_type: Mapped[str] = mapped_column(String(100))  # MIME type

  # Optional association with training job
  training_job_id: Mapped[int | None] = mapped_column(default=None)

  # Metadata
  description: Mapped[str | None] = mapped_column(String(500), default=None)
  metadata_: Mapped[dict | None] = mapped_column('metadata', JSON, default=None)  # Additional JSON metadata
