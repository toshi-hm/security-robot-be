"""Helpers for serving lightweight playback data from JSONL logs."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import re
from typing import Any

LOG_ROOT = Path("report/result")
LOG_PATTERN = re.compile(r"job_(\d+)_episodes\.jsonl$")


@dataclass(frozen=True)
class LogPlaybackMetadata:
  session_id: int
  path: Path
  episode_count: int
  last_step: int
  recorded_at: datetime


def list_log_playback_files() -> dict[int, Path]:
  """Return mapping from session_id to JSONL log path."""

  if not LOG_ROOT.exists():
    return {}

  mapping: dict[int, Path] = {}
  for path in LOG_ROOT.glob("job_*_episodes.jsonl"):
    match = LOG_PATTERN.match(path.name)
    if not match:
      continue
    session_id = int(match.group(1))
    mapping[session_id] = path
  return mapping


def read_log_metadata(path: Path) -> LogPlaybackMetadata:
  """Compute summary metadata for the JSONL playback log."""

  episode_count = 0
  last_step = 0
  with path.open("r", encoding="utf-8") as handle:
    for line in handle:
      if not line.strip():
        continue
      episode_count += 1
      try:
        payload = json.loads(line)
      except json.JSONDecodeError:
        continue
      steps = payload.get("steps")
      if isinstance(steps, int) and steps > last_step:
        last_step = steps

  recorded_at = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
  return LogPlaybackMetadata(
    session_id=_extract_session_id(path),
    path=path,
    episode_count=episode_count,
    last_step=last_step,
    recorded_at=recorded_at,
  )


def _extract_session_id(path: Path) -> int:
  match = LOG_PATTERN.match(path.name)
  if not match:
    raise ValueError(f"Unsupported log filename: {path.name}")
  return int(match.group(1))


def load_log_entries(
  path: Path,
  *,
  offset: int,
  limit: int,
) -> tuple[list[dict[str, Any]], int]:
  """Load a window of entries and return the total count."""

  entries: list[dict[str, Any]] = []
  total = 0
  with path.open("r", encoding="utf-8") as handle:
    for line in handle:
      if not line.strip():
        continue
      total += 1
      if total <= offset:
        continue
      if len(entries) >= limit:
        continue
      try:
        payload = json.loads(line)
      except json.JSONDecodeError:
        continue
      payload["_episode"] = total
      entries.append(payload)
  return entries, total


def build_log_frames(
  session_id: int,
  entries: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
  """Convert log entries into EnvironmentState-like payloads."""

  entries_list = list(entries)
  grid_size = _infer_grid_size(entries_list)
  threat_grid = [[0 for _ in range(grid_size)] for _ in range(grid_size)]

  base_time = datetime.now(tz=UTC)
  frames: list[dict[str, Any]] = []
  for index, entry in enumerate(entries_list):
    episode = int(entry.get("_episode", index + 1))
    start_positions = entry.get("start_positions") or []
    robots = _build_robot_states(start_positions)
    primary_robot = robots[0] if robots else {"x": 0, "y": 0}

    created_at = base_time + timedelta(seconds=episode)
    frames.append(
      {
        "id": -(session_id * 100000 + episode),
        "session_id": session_id,
        "episode": max(episode - 1, 0),
        "step": int(entry.get("steps") or 0),
        "robot_x": int(primary_robot.get("x", 0)),
        "robot_y": int(primary_robot.get("y", 0)),
        "robot_orientation": 0,
        "robots": robots,
        "charging_stations": None,
        "threat_grid": {"levels": threat_grid},
        "coverage_map": None,
        "obstacles": None,
        "suspicious_objects": [],
        "action_taken": None,
        "reward_received": float(entry.get("final_reward") or 0.0),
        "coverage_ratio": _to_float(entry.get("coverage")),
        "exploration_score": None,
        "battery_percentage": None,
        "is_charging": False,
        "distance_to_charging_station": None,
        "charging_station_position_x": None,
        "charging_station_position_y": None,
        "created_at": created_at,
        "updated_at": created_at,
      }
    )
  return frames


def _infer_grid_size(entries: Iterable[dict[str, Any]]) -> int:
  max_coord = 0
  for entry in entries:
    positions = entry.get("start_positions") or []
    for pos in positions:
      if not isinstance(pos, (list, tuple)) or len(pos) < 2:
        continue
      try:
        max_coord = max(max_coord, int(pos[0]), int(pos[1]))
      except (TypeError, ValueError):
        continue
  return max(8, max_coord + 1)


def _build_robot_states(start_positions: Iterable[Any]) -> list[dict[str, Any]]:
  robots: list[dict[str, Any]] = []
  for robot_id, pos in enumerate(start_positions):
    if not isinstance(pos, (list, tuple)) or len(pos) < 2:
      continue
    try:
      x = int(pos[0])
      y = int(pos[1])
    except (TypeError, ValueError):
      continue
    robots.append({"id": robot_id, "x": x, "y": y, "orientation": 0})
  return robots


def _to_float(value: Any) -> float | None:
  if value is None:
    return None
  try:
    return float(value)
  except (TypeError, ValueError):
    return None
