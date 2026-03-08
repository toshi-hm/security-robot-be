from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any


def _parse_datetime(value: str | None) -> datetime | None:
  if not value:
    return None
  normalized = value.replace("Z", "+00:00")
  return datetime.fromisoformat(normalized)


def _load_export(path: Path) -> dict[str, Any]:
  with path.open("r", encoding="utf-8") as f:
    payload = json.load(f)
  if not isinstance(payload, dict) or "sessions" not in payload:
    raise ValueError("Export JSON must contain a top-level 'sessions' list.")
  return payload


def _build_job_payload(session_data: dict[str, Any]) -> dict[str, Any]:
  return {
    "id": session_data.get("id"),
    "name": session_data.get("name"),
    "algorithm": session_data.get("algorithm"),
    "environment_type": session_data.get("environment_type"),
    "status": session_data.get("status"),
    "total_timesteps": session_data.get("total_timesteps", 0),
    "current_timestep": session_data.get("current_timestep", 0),
    "episodes_completed": session_data.get("episodes_completed", 0),
    "env_width": session_data.get("env_width", 8),
    "env_height": session_data.get("env_height", 8),
    "num_robots": session_data.get("num_robots", 1),
    "coverage_weight": session_data.get("coverage_weight", 1.5),
    "exploration_weight": session_data.get("exploration_weight", 3.0),
    "diversity_weight": session_data.get("diversity_weight", 2.0),
    "learning_rate": session_data.get("learning_rate", 0.0003),
    "batch_size": session_data.get("batch_size", 64),
    "num_workers": session_data.get("num_workers", 1),
    "model_path": session_data.get("model_path"),
    "log_path": session_data.get("log_path"),
    "config": session_data.get("config"),
    "created_at": _parse_datetime(session_data.get("created_at")),
    "updated_at": _parse_datetime(session_data.get("updated_at")),
    "started_at": _parse_datetime(session_data.get("started_at")),
    "completed_at": _parse_datetime(session_data.get("completed_at")),
  }


def _build_metric_payload(metric_data: dict[str, Any], job_id: int) -> dict[str, Any]:
  return {
    "job_id": metric_data.get("job_id", job_id),
    "timestep": metric_data.get("timestep"),
    "episode": metric_data.get("episode"),
    "reward": metric_data.get("reward"),
    "loss": metric_data.get("loss"),
    "coverage_ratio": metric_data.get("coverage_ratio"),
    "exploration_score": metric_data.get("exploration_score"),
    "threat_level_avg": metric_data.get("threat_level_avg"),
    "additional_metrics": metric_data.get("additional_metrics"),
    "timestamp": _parse_datetime(metric_data.get("timestamp")) or datetime.utcnow(),
    "created_at": _parse_datetime(metric_data.get("created_at")),
    "updated_at": _parse_datetime(metric_data.get("updated_at")),
  }


def _parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Import training data from a DB export JSON.")
  parser.add_argument(
    "--export-path",
    type=Path,
    default=Path("backup_extracted/backup_20251213_141144/data/db_export.json"),
    help="Path to db_export.json extracted from the backup archive.",
  )
  parser.add_argument(
    "--database-url",
    type=str,
    default=None,
    help="Override DATABASE_URL (e.g. postgresql+psycopg://user:pass@localhost:5432/db).",
  )
  parser.add_argument(
    "--mode",
    choices=("skip", "merge", "replace"),
    default="merge",
    help="Import mode: skip existing jobs, merge metrics into existing jobs, or replace jobs.",
  )
  parser.add_argument(
    "--dry-run",
    action="store_true",
    help="Show what would be imported without writing to the database.",
  )
  parser.add_argument(
    "--no-skip-duplicate-metrics",
    action="store_true",
    help="Insert metrics even if the (timestep, episode) pair already exists for a job.",
  )
  return parser.parse_args()


def main() -> None:
  args = _parse_args()

  if args.database_url:
    os.environ["DATABASE_URL"] = args.database_url

  from sqlalchemy import select

  from app.db.session import SessionLocal
  from app.models.training import TrainingJob, TrainingMetric

  export = _load_export(args.export_path)
  sessions = export.get("sessions", [])

  job_created = 0
  job_skipped = 0
  job_replaced = 0
  metric_inserted = 0
  metric_skipped = 0

  with SessionLocal() as session:
    for session_data in sessions:
      job_id = session_data.get("id")
      if job_id is None:
        continue

      existing_job = session.get(TrainingJob, job_id)
      if existing_job:
        if args.mode == "skip":
          job_skipped += 1
          continue
        if args.mode == "replace":
          if not args.dry_run:
            session.delete(existing_job)
            session.flush()
          job_replaced += 1
      else:
        job_created += 1

      if not existing_job or args.mode in ("replace", "merge"):
        if not existing_job or args.mode == "replace":
          job_payload = _build_job_payload(session_data)
          if not args.dry_run:
            session.add(TrainingJob(**job_payload))

      metrics = session_data.get("metrics", []) or []
      existing_metric_keys: set[tuple[int | None, int | None]] = set()
      if existing_job and args.mode == "merge":
        existing_metric_keys = set(
          session.execute(
            select(TrainingMetric.timestep, TrainingMetric.episode).where(
              TrainingMetric.job_id == job_id
            )
          ).all()
        )

      for metric_data in metrics:
        if not args.no_skip_duplicate_metrics and existing_metric_keys:
          metric_key = (
            metric_data.get("timestep"),
            metric_data.get("episode"),
          )
          if metric_key in existing_metric_keys:
            metric_skipped += 1
            continue
        metric_inserted += 1
        if not args.dry_run:
          metric_payload = _build_metric_payload(metric_data, job_id)
          session.add(TrainingMetric(**metric_payload))

    if not args.dry_run:
      session.commit()

  print(
    "Import summary:",
    f"jobs_created={job_created}",
    f"jobs_replaced={job_replaced}",
    f"jobs_skipped={job_skipped}",
    f"metrics_inserted={metric_inserted}",
    f"metrics_skipped={metric_skipped}",
    sep="\n- ",
  )


if __name__ == "__main__":
  main()
