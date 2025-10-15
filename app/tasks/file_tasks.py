"""Celery tasks that operate on stored artefacts (logs, models, etc.)."""

from __future__ import annotations

import logging
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.core.files import storage
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

ARCHIVE_ROOT = (storage.STORAGE_ROOT / 'archives').resolve()
ARCHIVE_ROOT.mkdir(parents=True, exist_ok=True)


def _validate_source(path: str) -> Path:
  source = Path(path).expanduser()
  if not source.exists():
    raise ValueError(f'Path does not exist: {path}')
  if not (source.is_file() or source.is_dir()):
    raise ValueError(f'Path must point to a file or directory: {path}')
  return source


def _sanitize_segment(value: str, *, fallback: str) -> str:
  sanitized = Path(value).name.strip().replace(' ', '_')
  return sanitized or fallback


def _build_archive_path(source: Path) -> Path:
  stem = source.stem if source.is_file() else source.name
  safe_stem = _sanitize_segment(stem or 'logs', fallback='logs')

  timestamp = datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')
  unique = uuid4().hex
  archive_dir = ARCHIVE_ROOT / safe_stem
  archive_dir.mkdir(parents=True, exist_ok=True)
  archive_name = f'{safe_stem}_{timestamp}_{unique}.zip'
  return archive_dir / archive_name


def _add_directory_contents(archive: zipfile.ZipFile, root: Path) -> None:
  for item in root.rglob('*'):
    if item.is_dir():
      # Skip directory entries; ZipFile will create them implicitly for files.
      continue
    archive.write(item, arcname=item.relative_to(root).as_posix())


def _add_file(archive: zipfile.ZipFile, file_path: Path) -> None:
  archive.write(file_path, arcname=file_path.name)


@celery_app.task(name='files.archive_logs')
def archive_logs(path: str) -> str:
  """Archive a log file or directory into a ZIP bundle.

  Args:
    path: Absolute or relative path to a log file/directory.

  Returns:
    The absolute path to the created archive as a string.
  """

  source = _validate_source(path)
  archive_path = _build_archive_path(source)

  archive_path.parent.mkdir(parents=True, exist_ok=True)

  with zipfile.ZipFile(archive_path, mode='w', compression=zipfile.ZIP_DEFLATED) as archive:
    if source.is_dir():
      _add_directory_contents(archive, source)
    else:
      _add_file(archive, source)

  logger.info('Archived logs from %s to %s', source, archive_path)
  return archive_path.as_posix()


__all__ = ['archive_logs']
