"""Low-level file storage utilities for binary assets."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from starlette.datastructures import UploadFile

from app.core.files import storage


class FileStorageService:
  """Persist uploaded files to the configured storage root."""

  def _storage_root(self) -> Path:
    root = storage.STORAGE_ROOT
    root.mkdir(parents=True, exist_ok=True)
    return root

  def _sanitize_segment(self, value: str, *, fallback: str) -> str:
    sanitized = Path(value).name
    return sanitized or fallback

  def _generate_filename(self, original_name: str) -> str:
    safe_name = self._sanitize_segment(original_name or 'upload.bin', fallback='upload')
    stem = Path(safe_name).stem or 'upload'
    suffix = Path(safe_name).suffix
    return f"{uuid4().hex}_{stem}{suffix}" if suffix else f"{uuid4().hex}_{stem}"

  async def save_upload(self, upload: UploadFile, *, file_type: str) -> tuple[str, str, int, str]:
    """Store an uploaded file and return metadata information.

    Returns a tuple of (stored_filename, relative_path, file_size, content_type).
    """

    content = await upload.read()
    content_type = upload.content_type or 'application/octet-stream'

    safe_type = self._sanitize_segment(file_type or 'misc', fallback='misc')
    filename = self._generate_filename(upload.filename or 'upload.bin')
    relative_path = Path(safe_type) / filename
    absolute_path = self._storage_root() / relative_path
    absolute_path.parent.mkdir(parents=True, exist_ok=True)
    absolute_path.write_bytes(content)

    # Reset the file pointer for potential re-use by callers
    await upload.seek(0)

    return filename, relative_path.as_posix(), len(content), content_type

  def delete(self, relative_path: str) -> None:
    """Remove a stored file if it exists."""

    if not relative_path:
      return

    absolute_path = self._storage_root() / Path(relative_path)
    try:
      absolute_path.unlink()
    except FileNotFoundError:
      return

  def resolve(self, relative_path: str) -> Path:
    """Return the absolute path for the given relative storage path."""

    absolute = (self._storage_root() / Path(relative_path)).resolve()
    root = self._storage_root().resolve()
    if not str(absolute).startswith(str(root)):
      raise ValueError('Invalid file path outside storage root')
    if not absolute.exists():
      raise FileNotFoundError(relative_path)
    return absolute


file_storage_service = FileStorageService()

__all__ = ['FileStorageService', 'file_storage_service']
