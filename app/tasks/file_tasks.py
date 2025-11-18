"""Celery tasks that operate on stored artefacts (logs, models, etc.)."""

from __future__ import annotations

from datetime import UTC, datetime
import json
import logging
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from uuid import uuid4
import zipfile

from sqlalchemy import exc as sa_exc
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.files import storage
from app.db.session import SessionLocal
from app.models.environment import EnvironmentState
from app.models.files import FileMetadata
from app.models.training import TrainingJob
from app.tasks.celery_app import celery_app
from app.tasks.training_tasks import _create_redis_client, _publish_training_event

logger = logging.getLogger(__name__)

ARCHIVE_ROOT = (storage.STORAGE_ROOT / "archives").resolve()
ARCHIVE_ROOT.mkdir(parents=True, exist_ok=True)

PLAYBACK_ARCHIVE_ROOT = (storage.STORAGE_ROOT / "playback_archives").resolve()
PLAYBACK_ARCHIVE_ROOT.mkdir(parents=True, exist_ok=True)


def _validate_source(path: str) -> Path:
  source = Path(path).expanduser()
  if not source.exists():
    raise ValueError(f"Path does not exist: {path}")
  if not (source.is_file() or source.is_dir()):
    raise ValueError(f"Path must point to a file or directory: {path}")
  return source


def _sanitize_segment(value: str, *, fallback: str) -> str:
  sanitized = Path(value).name.strip().replace(" ", "_")
  return sanitized or fallback


def _build_archive_path(source: Path) -> Path:
  stem = source.stem if source.is_file() else source.name
  safe_stem = _sanitize_segment(stem or "logs", fallback="logs")

  timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
  unique = uuid4().hex
  archive_dir = ARCHIVE_ROOT / safe_stem
  archive_dir.mkdir(parents=True, exist_ok=True)
  archive_name = f"{safe_stem}_{timestamp}_{unique}.zip"
  return archive_dir / archive_name


def _build_playback_archive_path(session_id: int) -> Path:
  safe_segment = _sanitize_segment(f"session_{session_id}", fallback="session")
  timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
  unique = uuid4().hex
  archive_dir = PLAYBACK_ARCHIVE_ROOT / safe_segment
  archive_dir.mkdir(parents=True, exist_ok=True)
  archive_name = f"{safe_segment}_{timestamp}_{unique}.zip"
  return archive_dir / archive_name


def _add_directory_contents(archive: zipfile.ZipFile, root: Path) -> None:
  for item in root.rglob("*"):
    if item.is_dir():
      # Skip directory entries; ZipFile will create them implicitly for files.
      continue
    archive.write(item, arcname=item.relative_to(root).as_posix())


def _add_file(archive: zipfile.ZipFile, file_path: Path) -> None:
  archive.write(file_path, arcname=file_path.name)


def _serialize_environment_state(state: EnvironmentState) -> dict[str, Any]:
  return {
    "id": state.id,
    "session_id": state.session_id,
    "episode": state.episode,
    "step": state.step,
    "robot_x": state.robot_x,
    "robot_y": state.robot_y,
    "robot_orientation": state.robot_orientation,
    "threat_grid": state.threat_grid,
    "coverage_map": state.coverage_map,
    "suspicious_objects": state.suspicious_objects,
    "action_taken": state.action_taken,
    "reward_received": state.reward_received,
    "battery_percentage": state.battery_percentage,
    "is_charging": state.is_charging,
    "distance_to_charging_station": state.distance_to_charging_station,
    "charging_station_position_x": state.charging_station_position_x,
    "charging_station_position_y": state.charging_station_position_y,
    "created_at": state.created_at.isoformat() if state.created_at else None,
    "updated_at": state.updated_at.isoformat() if state.updated_at else None,
  }


def _purge_environment_states(db: Session, session_id: int, *, batch_size: int) -> int:
  """Delete environment state records in batches to avoid long-running locks."""

  total_deleted = 0
  while True:
    id_batch = (
      db.execute(
        select(EnvironmentState.id)
        .where(EnvironmentState.session_id == session_id)
        .order_by(EnvironmentState.id.asc())
        .limit(batch_size)
      )
      .scalars()
      .all()
    )
    if not id_batch:
      break

    deleted = (
      db.query(EnvironmentState)
      .filter(EnvironmentState.id.in_(id_batch))
      .delete(synchronize_session=False)
    )
    total_deleted += deleted
    db.flush()

  return total_deleted


@celery_app.task(name="files.archive_logs")
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

  with zipfile.ZipFile(archive_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
    if source.is_dir():
      _add_directory_contents(archive, source)
    else:
      _add_file(archive, source)

  logger.info("Archived logs from %s to %s", source, archive_path)
  return archive_path.as_posix()


@celery_app.task(
  name="playback.archive_session",
  autoretry_for=(OSError, sa_exc.OperationalError),
  retry_kwargs={"max_retries": 3, "countdown": 60},
  retry_backoff=True,
)
def archive_playback_session(session_id: int) -> dict[str, Any]:
  """Export playback frames for a session and register the archive."""

  archive_path: Path | None = None
  db: Session = SessionLocal()
  try:
    chunk_size = settings.playback_archive_chunk_size
    delete_batch_size = settings.playback_archive_delete_batch_size
    max_archive_size = settings.playback_archive_max_bytes
    max_expansion_ratio = settings.playback_archive_max_expansion_ratio

    if not isinstance(session_id, int) or session_id <= 0:
      raise ValueError(f"Invalid session_id: {session_id}")

    job = db.get(TrainingJob, session_id)
    if job is None:
      raise ValueError(f"Training session {session_id} not found")

    frame_count = (
      db.query(EnvironmentState).filter(EnvironmentState.session_id == session_id).count()
    )
    if frame_count == 0:
      raise ValueError(f"No playback frames recorded for session {session_id}")

    transaction_id = getattr(archive_playback_session.request, "id", None) or uuid4().hex

    logger.info("Exporting %d frames for playback session %s", frame_count, session_id)

    states_stmt = (
      select(EnvironmentState)
      .where(EnvironmentState.session_id == session_id)
      .order_by(
        EnvironmentState.episode.asc(),
        EnvironmentState.step.asc(),
        EnvironmentState.id.asc(),
      )
      .execution_options(yield_per=chunk_size, stream_results=True)
    )

    archive_path = _build_playback_archive_path(session_id)
    archive_path.parent.mkdir(parents=True, exist_ok=True)

    with TemporaryDirectory() as tmpdir:
      jsonl_path = Path(tmpdir) / "frames.jsonl"
      with jsonl_path.open("w", encoding="utf-8") as buffer:
        for idx, state in enumerate(db.execute(states_stmt).scalars(), start=1):
          json.dump(
            _serialize_environment_state(state),
            buffer,
            ensure_ascii=False,
            separators=(",", ":"),
          )
          buffer.write("\n")
          if idx % chunk_size == 0 or idx == frame_count:
            logger.debug("Exported %d/%d frames for session %s", idx, frame_count, session_id)

      uncompressed_size = jsonl_path.stat().st_size
      max_expanded_bytes = max_archive_size * max_expansion_ratio
      if uncompressed_size > max_expanded_bytes:
        logger.error(
          "Playback archive payload for session %s exceeds expansion limit " "(%d > %d bytes)",
          session_id,
          uncompressed_size,
          max_expanded_bytes,
        )
        raise ValueError(
          "Playback archive payload exceeds allowable expansion ratio and was not created"
        )

      try:
        with zipfile.ZipFile(archive_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
          archive.write(jsonl_path, arcname="frames.jsonl")
      except (OSError, zipfile.BadZipFile) as exc:
        safe_label = archive_path.name
        exc_info = exc if logger.isEnabledFor(logging.DEBUG) else None
        logger.error(
          "Failed to create archive for session %s (%s): %s",
          session_id,
          safe_label,
          exc,
          exc_info=exc_info,
        )
        raise

    archive_size = archive_path.stat().st_size
    if archive_size > max_archive_size:
      logger.error(
        "Archive %s for session %s exceeds max size %d bytes (actual: %d)",
        archive_path,
        session_id,
        max_archive_size,
        archive_size,
      )
      raise ValueError(
        f"Archive for session {session_id} exceeds maximum size of {max_archive_size} bytes"
      )

    relative_path = archive_path.resolve().relative_to(storage.STORAGE_ROOT.resolve())
    file_record = FileMetadata(
      filename=archive_path.name,
      original_filename=archive_path.name,
      file_path=relative_path.as_posix(),
      file_size=archive_size,
      file_type="archives",
      content_type="application/zip",
      training_job_id=session_id,
      description=f"Playback archive for session {session_id}",
      metadata_={
        "session_id": session_id,
        "frame_count": frame_count,
        "format": "jsonl",
        "transaction_id": transaction_id,
      },
    )

    db.add(file_record)
    deleted_states = _purge_environment_states(
      db,
      session_id,
      batch_size=delete_batch_size,
    )
    logger.debug(
      "Deleted %d environment states for session %s after archiving playback data",
      deleted_states,
      session_id,
    )
    db.commit()

    redis_client = _create_redis_client()
    _publish_training_event(
      redis_client,
      session_id,
      {
        "event": "playback_archived",
        "file_id": file_record.id,
        "file_path": file_record.file_path,
        "frame_count": frame_count,
        "transaction_id": transaction_id,
      },
      critical=True,
    )

    logger.info("Archived playback session %s to %s", session_id, archive_path)
    return {
      "file_id": file_record.id,
      "file_path": file_record.file_path,
      "frame_count": frame_count,
    }
  except Exception:
    db.rollback()
    if archive_path is not None and archive_path.exists():
      archive_path.unlink(missing_ok=True)
    raise
  finally:
    db.close()


__all__ = ["archive_logs", "archive_playback_session"]
