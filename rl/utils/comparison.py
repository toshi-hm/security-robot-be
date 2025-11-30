"""Utility helpers for comparing template agents with RL agents."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
import logging
from statistics import mean, stdev
from typing import Any

from rl.agents.template_agents import BaseTemplateAgent
from rl.environments.security_env import SecurityEnvironment, calculate_dynamic_max_steps

logger = logging.getLogger(__name__)
PROGRESS_STEP_INTERVAL = 10


@dataclass
class EvaluationMetrics:
  """Metrics collected during agent evaluation."""

  total_reward: float = 0.0
  episode_length: int = 0
  coverage_ratio: float = 0.0
  patrol_count: int = 0
  move_count: int = 0
  turn_count: int = 0
  battery_deaths: int = 0
  min_battery: float = 100.0
  charging_events: int = 0


@dataclass
class FrameData:
  """Snapshot of a single timestep during playback."""

  timestep: int
  robot_x: int
  robot_y: int
  robot_orientation: int
  action: int
  reward: float
  battery_percentage: float
  is_charging: bool
  coverage_map: list[list[int]]
  timestamp: str

  def to_dict(self) -> dict[str, Any]:
    return {
      "timestep": self.timestep,
      "robot_x": self.robot_x,
      "robot_y": self.robot_y,
      "robot_orientation": self.robot_orientation,
      "action": self.action,
      "reward": self.reward,
      "battery_percentage": self.battery_percentage,
      "is_charging": self.is_charging,
      "coverage_map": self.coverage_map,
      "timestamp": self.timestamp,
    }


@dataclass
class EpisodePlayback:
  """Playback data for a single episode."""

  episode: int
  frames: list[FrameData] = field(default_factory=list)
  total_reward: float = 0.0
  final_coverage: float = 0.0
  episode_length: int = 0

  def to_dict(self) -> dict[str, Any]:
    return {
      "episode": self.episode,
      "frames": [frame.to_dict() for frame in self.frames],
      "total_reward": self.total_reward,
      "final_coverage": self.final_coverage,
      "episode_length": self.episode_length,
    }


@dataclass
class EnvironmentInfo:
  """Static information about an environment."""

  width: int
  height: int
  threat_grid: list[list[float]]
  average_threat_level: float
  max_threat_level: float
  min_threat_level: float
  threat_histogram: list[int]
  high_threat_tiles: list[dict[str, Any]]
  obstacles: list[list[bool]]
  charging_station: dict[str, int]
  suspicious_objects: list[dict[str, Any]]

  def to_dict(self) -> dict[str, Any]:
    return {
      "width": self.width,
      "height": self.height,
      "threat_grid": self.threat_grid,
      "average_threat_level": self.average_threat_level,
      "max_threat_level": self.max_threat_level,
      "min_threat_level": self.min_threat_level,
      "threat_histogram": self.threat_histogram,
      "high_threat_tiles": self.high_threat_tiles,
      "obstacles": self.obstacles,
      "charging_station": self.charging_station,
      "suspicious_objects": self.suspicious_objects,
    }


ProgressCallback = Callable[[dict[str, Any]], None]


@dataclass
class ComparisonResult:
  """Result of comparing multiple agents."""

  agent_name: str
  episodes: int
  metrics: list[EvaluationMetrics] = field(default_factory=list)
  playbacks: list[EpisodePlayback] = field(default_factory=list)
  environment_info: EnvironmentInfo | None = None

  @property
  def avg_reward(self) -> float:
    """Average total reward across episodes."""
    if not self.metrics:
      return 0.0
    return mean(m.total_reward for m in self.metrics)

  @property
  def std_reward(self) -> float:
    """Standard deviation of rewards."""
    if len(self.metrics) < 2:
      return 0.0
    return stdev(m.total_reward for m in self.metrics)

  @property
  def avg_coverage(self) -> float:
    """Average coverage ratio."""
    if not self.metrics:
      return 0.0
    return mean(m.coverage_ratio for m in self.metrics)

  @property
  def avg_episode_length(self) -> float:
    """Average episode length."""
    if not self.metrics:
      return 0.0
    return mean(m.episode_length for m in self.metrics)

  @property
  def avg_patrol_count(self) -> float:
    """Average number of patrol actions."""
    if not self.metrics:
      return 0.0
    return mean(m.patrol_count for m in self.metrics)

  @property
  def avg_min_battery(self) -> float:
    """Average minimum battery percentage."""
    if not self.metrics:
      return 0.0
    return mean(m.min_battery for m in self.metrics)

  @property
  def total_battery_deaths(self) -> int:
    """Total number of battery deaths."""
    return sum(m.battery_deaths for m in self.metrics)

  def to_dict(self) -> dict[str, Any]:
    """Convert to dictionary for JSON serialization."""
    data = {
      "agent_name": self.agent_name,
      "episodes": self.episodes,
      "average_reward": self.avg_reward,
      "std_reward": self.std_reward,
      "average_coverage": self.avg_coverage,
      "average_episode_length": self.avg_episode_length,
      "average_patrol_count": self.avg_patrol_count,
      "average_min_battery": self.avg_min_battery,
      "total_battery_deaths": self.total_battery_deaths,
    }
    if self.environment_info is not None:
      data["environment_info"] = self.environment_info.to_dict()
    if self.playbacks:
      data["episode_playbacks"] = [playback.to_dict() for playback in self.playbacks]
    return data


def evaluate_template_agent(
  agent: BaseTemplateAgent,
  env: SecurityEnvironment,
  *,
  episodes: int = 10,
  max_steps: int | None = None,
  seed: int | None = None,
  save_frames: bool = False,
  progress_callback: ProgressCallback | None = None,
  progress_step_interval: int = PROGRESS_STEP_INTERVAL,
) -> ComparisonResult:
  """
  Evaluate a template-based agent on the security environment.

  Args:
      agent: Template agent to evaluate
      env: SecurityEnvironment instance
      episodes: Number of episodes to run
      max_steps: Maximum steps per episode (None = use environment limit)
      seed: Random seed for environment reset
      save_frames: Whether to retain per-step playback data
      progress_callback: Optional callable for streaming progress updates
      progress_step_interval: Frequency for emitting step progress events

  Returns:
      ComparisonResult with collected metrics
  """
  result = ComparisonResult(
    agent_name=agent.__class__.__name__,
    episodes=episodes,
  )

  progress_interval = max(1, progress_step_interval)

  effective_max_steps = max_steps
  if effective_max_steps is None:
    env_limit = getattr(env, "max_episode_steps", None)
    if env_limit is not None:
      effective_max_steps = int(env_limit)
    else:
      effective_max_steps = calculate_dynamic_max_steps(env.width, env.height)

  def emit(event_type: str, **payload: Any) -> None:
    if progress_callback is None:
      return
    message = {"type": event_type, **payload}
    try:
      progress_callback(message)
    except Exception:  # pragma: no cover - defensive guardrail
      logger.debug("Failed to emit template agent progress event", exc_info=True)

  emit(
    "execution_started",
    total_episodes=episodes,
    total_steps_per_episode=effective_max_steps,
  )

  env_info_captured = False

  import copy

  # Create agents for each robot
  # We use deepcopy to ensure each robot has its own agent instance with independent state
  agents: list[Any] = [agent] + [copy.deepcopy(agent) for _ in range(env.num_robots - 1)]

  for episode in range(episodes):
    episode_seed = (seed + episode) if seed is not None else None
    env.reset(seed=episode_seed)

    # Reset all agents
    for a in agents:
      a.reset()

    if not env_info_captured:
      result.environment_info = _capture_environment_info(env)
      env_info_captured = True

    obstacle_coords = {
      (x, y) for y in range(env.height) for x in range(env.width) if env.obstacles[y][x]
    }

    metrics = EvaluationMetrics()
    frames: list[FrameData] = [] if save_frames else []
    emit("episode_started", episode=episode + 1)
    cumulative_reward = 0.0

    # Convert obstacles grid to set of coordinates for template agents
    obstacle_set = set()
    if hasattr(env, "obstacles"):
      for y in range(len(env.obstacles)):
        for x in range(len(env.obstacles[0])):
          if env.obstacles[y][x]:
            obstacle_set.add((x, y))

    for step in range(effective_max_steps):  # noqa: B007
      # Get robot state (Multi-agent compatible)
      if hasattr(env, "robot_positions"):
        robot_positions = env.robot_positions
        robot_directions = env.robot_directions
      else:
        # Legacy single-agent fallback
        robot_positions = [(env.robot_x, env.robot_y)]
        robot_directions = [env.robot_direction]

      # Collect actions for all robots
      actions = []
      for i in range(len(robot_positions)):
        # Use separate agent instance for each robot to maintain independent state
        agent_instance = agents[i]

        # Get action for this robot
        # Note: Template agents do not use battery or charging station info
        action = agent_instance.get_action(
          robot_positions[i][0], robot_positions[i][1], robot_directions[i], obstacle_set
        )
        actions.append(action)

        # Update metrics for each robot
        if action == 0:
          metrics.move_count += 1
        elif action in [1, 2]:
          metrics.turn_count += 1
        elif action == 3:
          metrics.patrol_count += 1

      _obs, reward, terminated, truncated, info = env.step(actions)
      reward_value = float(reward)
      metrics.total_reward += reward_value
      cumulative_reward += reward_value

      # Metrics aggregation (using min/sum as appropriate)
      # Min battery across all robots
      current_min_battery = min(env.battery_levels)
      metrics.min_battery = min(metrics.min_battery, current_min_battery)

      # Count charging events
      charging_count = sum(1 for is_charging in env.is_charging_list if is_charging)
      metrics.charging_events += charging_count

      if save_frames:
        # Note: FrameData currently supports single robot visualization.
        # We log Robot 0's data for backward compatibility.
        # Future TODO: Update FrameData to support multi-agent visualization.
        frames.append(
          FrameData(
            timestep=step,
            robot_x=int(env.robot_positions[0][0]),
            robot_y=int(env.robot_positions[0][1]),
            robot_orientation=int(env.robot_directions[0]),
            action=int(actions[0]),
            reward=reward_value,
            battery_percentage=float(env.battery_levels[0]),
            is_charging=bool(env.is_charging_list[0]),
            coverage_map=_copy_grid(getattr(env, "last_patrolled", []), cast_func=int),
            timestamp=_iso_timestamp(),
          )
        )

      current_step = step + 1
      if (
        current_step % progress_interval == 0
        or terminated
        or truncated
        or current_step == effective_max_steps
      ):
        # Use Robot 0 battery for progress update consistency
        battery = float(env.battery_levels[0])
        emit(
          "step_update",
          episode=episode + 1,
          step=current_step,
          current_reward=cumulative_reward,
          current_coverage=_calculate_coverage_ratio(env, obstacle_coords),
          battery_percentage=battery,
        )

      if terminated or truncated:
        # Check if ANY robot died
        if any(b <= 0 for b in env.battery_levels):
          metrics.battery_deaths += 1
        break

    total_cells = env.width * env.height - len(obstacle_coords)
    patrolled_cells = sum(
      1
      for y in range(env.height)
      for x in range(env.width)
      if env.last_patrolled[y][x] > 0 and (x, y) not in obstacle_coords
    )
    metrics.coverage_ratio = patrolled_cells / total_cells if total_cells > 0 else 0.0
    metrics.episode_length = step + 1

    if save_frames:
      result.playbacks.append(
        EpisodePlayback(
          episode=episode + 1,
          frames=frames,
          total_reward=metrics.total_reward,
          final_coverage=metrics.coverage_ratio,
          episode_length=metrics.episode_length,
        )
      )

    result.metrics.append(metrics)
    emit(
      "episode_completed",
      episode=episode + 1,
      total_reward=metrics.total_reward,
      coverage=metrics.coverage_ratio,
      episode_length=metrics.episode_length,
    )

  emit(
    "execution_completed",
    episodes=result.episodes,
    average_reward=result.avg_reward,
    average_coverage=result.avg_coverage,
  )

  return result


def _copy_grid(
  grid: Any,
  *,
  cast_func: Callable[[Any], Any] | None = None,
) -> list[list[Any]]:
  rows: list[list[Any]] = []
  for column in list(grid or []):
    converted_column: list[Any] = []
    for value in list(column or []):
      converted_value = value
      if cast_func is not None:
        try:
          converted_value = cast_func(value)
        except Exception:
          converted_value = value
      elif isinstance(value, (int, float)):
        converted_value = value
      converted_column.append(converted_value)
    rows.append(converted_column)
  return rows


def _copy_bool_grid(grid: Any) -> list[list[bool]]:
  rows: list[list[bool]] = []
  for column in list(grid or []):
    converted_column: list[bool] = []
    for value in list(column or []):
      converted_column.append(bool(value))
    rows.append(converted_column)
  return rows


def _serialise_suspicious_objects(mapping: Any) -> list[dict[str, Any]]:
  try:
    items = list(mapping.items())
  except AttributeError:
    return []

  serialised: list[dict[str, Any]] = []
  for coords, value in sorted(items):
    if isinstance(coords, (tuple, list)) and len(coords) >= 2:
      x, y = coords[:2]
    else:
      x, y = coords, None
    payload: dict[str, Any] = {"x": int(x), "y": int(y) if isinstance(y, (int, float)) else y}
    if isinstance(value, dict):
      payload.update(value)
    elif isinstance(value, (int, float)):
      payload["spawn_time"] = int(value)
    else:
      payload["value"] = value
    serialised.append(payload)
  return serialised


def _capture_environment_info(env: SecurityEnvironment) -> EnvironmentInfo:
  threat_grid = _copy_grid(getattr(env, "threat_levels", []), cast_func=float)
  avg_threat, max_threat, min_threat = _calculate_threat_stats(threat_grid)
  histogram = _calculate_threat_histogram(threat_grid)
  high_threat_tiles = _extract_high_threat_tiles(threat_grid)
  return EnvironmentInfo(
    width=int(env.width),
    height=int(env.height),
    threat_grid=threat_grid,
    average_threat_level=avg_threat,
    max_threat_level=max_threat,
    min_threat_level=min_threat,
    threat_histogram=histogram,
    high_threat_tiles=high_threat_tiles,
    obstacles=_copy_bool_grid(getattr(env, "obstacles", [])),
    charging_station={
      "x": int(getattr(env, "charging_station_x", 0)),
      "y": int(getattr(env, "charging_station_y", 0)),
    },
    suspicious_objects=_serialise_suspicious_objects(getattr(env, "suspicious_objects", {})),
  )


def _calculate_coverage_ratio(
  env: SecurityEnvironment,
  obstacle_coords: set[tuple[int, int]],
) -> float:
  walkable_cells = env.width * env.height - len(obstacle_coords)
  if walkable_cells <= 0:
    return 0.0
  patrolled_cells = sum(
    1
    for y in range(env.height)
    for x in range(env.width)
    if env.last_patrolled[y][x] > 0 and (x, y) not in obstacle_coords
  )
  return patrolled_cells / walkable_cells


def _iso_timestamp() -> str:
  return datetime.now(tz=UTC).isoformat()


def _calculate_threat_stats(threat_grid: list[list[float]]) -> tuple[float, float, float]:
  flat_values = [value for column in threat_grid for value in column]
  if not flat_values:
    return 0.0, 0.0, 0.0
  avg = float(sum(flat_values) / len(flat_values))
  return avg, max(flat_values), min(flat_values)


def _calculate_threat_histogram(threat_grid: list[list[float]], bins: int = 5) -> list[int]:
  counts = [0 for _ in range(bins)]
  if not threat_grid:
    return counts
  for column in threat_grid:
    for value in column:
      index = min(int(value * bins), bins - 1)
      counts[index] += 1
  return counts


def _extract_high_threat_tiles(
  threat_grid: list[list[float]],
  top_k: int = 5,
) -> list[dict[str, float]]:
  tiles: list[tuple[float, int, int]] = []
  for y, row in enumerate(threat_grid):
    for x, value in enumerate(row):
      tiles.append((value, x, y))
  tiles.sort(reverse=True, key=lambda entry: entry[0])
  selected = []
  for threat, x, y in tiles[:top_k]:
    selected.append({"x": x, "y": y, "threat": float(threat)})
  return selected


def compare_agents(
  agents: dict[str, BaseTemplateAgent],
  *,
  width: int = 10,
  height: int = 10,
  episodes: int = 10,
  max_steps: int | None = None,
  seed: int | None = None,
) -> dict[str, ComparisonResult]:
  """
  Compare multiple template agents on the same environment.

  Args:
      agents: Dictionary mapping agent names to agent instances
      width: Environment width
      height: Environment height
      episodes: Number of episodes per agent
      max_steps: Maximum steps per episode (None = dynamic based on grid size)
      seed: Random seed for reproducibility

  Returns:
      Dictionary mapping agent names to their evaluation results
  """
  # Calculate dynamic max steps if not specified
  effective_max_steps = max_steps
  if effective_max_steps is None:
    effective_max_steps = calculate_dynamic_max_steps(width, height)

  env = SecurityEnvironment(
    width=width,
    height=height,
    max_episode_steps=effective_max_steps,
  )
  results = {}

  for name, agent in agents.items():
    results[name] = evaluate_template_agent(
      agent,
      env,
      episodes=episodes,
      max_steps=effective_max_steps,
      seed=seed,
    )

  return results


def generate_comparison_report(results: dict[str, ComparisonResult]) -> str:
  """
  Generate a human-readable comparison report.

  Args:
      results: Dictionary of comparison results

  Returns:
      Formatted report string
  """
  lines = [
    "=" * 60,
    "Template Agent Comparison Report",
    "=" * 60,
    "",
  ]

  # Sort by average reward (descending)
  sorted_results = sorted(
    results.items(),
    key=lambda x: x[1].avg_reward,
    reverse=True,
  )

  for rank, (_name, result) in enumerate(sorted_results, 1):
    lines.extend(
      [
        f"Rank #{rank}: {result.agent_name}",
        "-" * 40,
        f"  Average Reward:       {result.avg_reward:>10.2f} (+/- {result.std_reward:.2f})",
        f"  Average Coverage:     {result.avg_coverage:>10.2%}",
        f"  Average Episode Len:  {result.avg_episode_length:>10.1f}",
        f"  Average Patrol Count: {result.avg_patrol_count:>10.1f}",
        f"  Average Min Battery:  {result.avg_min_battery:>10.1f}%",
        f"  Battery Deaths:       {result.total_battery_deaths:>10d}",
        "",
      ]
    )

  lines.extend(
    [
      "=" * 60,
      "Summary",
      "=" * 60,
    ]
  )

  if sorted_results:
    best_agent = sorted_results[0][1].agent_name
    best_reward = sorted_results[0][1].avg_reward
    lines.append(f"Best Performing Agent: {best_agent} (avg reward: {best_reward:.2f})")

    if len(sorted_results) > 1:
      worst_agent = sorted_results[-1][1].agent_name
      worst_reward = sorted_results[-1][1].avg_reward
      lines.append(f"Worst Performing Agent: {worst_agent} (avg reward: {worst_reward:.2f})")
      lines.append(f"Performance Gap: {best_reward - worst_reward:.2f}")

  return "\n".join(lines)


def run_benchmark(
  *,
  width: int = 10,
  height: int = 10,
  episodes: int = 10,
  max_steps: int | None = None,
  seed: int | None = 42,
  include_random: bool = True,
) -> tuple[dict[str, ComparisonResult], str]:
  """
  Run a benchmark comparison of all template agents.

  Args:
      width: Environment width
      height: Environment height
      episodes: Number of episodes per agent
      max_steps: Maximum steps per episode (None = dynamic based on grid size)
      seed: Random seed for reproducibility
      include_random: Whether to include RandomWalkAgent

  Returns:
      Tuple of (results dictionary, formatted report string)
  """
  from rl.agents.template_agents import (
    HorizontalScanAgent,
    RandomWalkAgent,
    SpiralAgent,
    VerticalScanAgent,
  )

  agents: dict[str, BaseTemplateAgent] = {
    "horizontal": HorizontalScanAgent(width, height),
    "vertical": VerticalScanAgent(width, height),
    "spiral": SpiralAgent(width, height),
  }

  if include_random:
    agents["random"] = RandomWalkAgent(width, height, seed=seed)

  results = compare_agents(
    agents,
    width=width,
    height=height,
    episodes=episodes,
    max_steps=max_steps,
    seed=seed,
  )

  report = generate_comparison_report(results)

  return results, report
