"""Utility helpers for comparing template agents with RL agents."""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean, stdev
from typing import Any

from rl.agents.template_agents import BaseTemplateAgent
from rl.environments.security_env import SecurityEnvironment


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
class ComparisonResult:
    """Result of comparing multiple agents."""

    agent_name: str
    episodes: int
    metrics: list[EvaluationMetrics] = field(default_factory=list)

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
        return {
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


def evaluate_template_agent(
    agent: BaseTemplateAgent,
    env: SecurityEnvironment,
    *,
    episodes: int = 10,
    max_steps: int = 1000,
    seed: int | None = None,
) -> ComparisonResult:
    """
    Evaluate a template-based agent on the security environment.

    Args:
        agent: Template agent to evaluate
        env: SecurityEnvironment instance
        episodes: Number of episodes to run
        max_steps: Maximum steps per episode
        seed: Random seed for environment reset

    Returns:
        ComparisonResult with collected metrics
    """
    result = ComparisonResult(
        agent_name=agent.__class__.__name__,
        episodes=episodes,
    )

    for episode in range(episodes):
        # Reset environment and agent
        episode_seed = (seed + episode) if seed is not None else None
        env.reset(seed=episode_seed)
        agent.reset()

        # Convert 2D boolean obstacle grid to set of coordinates
        obstacle_coords = {
            (x, y)
            for x in range(env.width)
            for y in range(env.height)
            if env.obstacles[x][y]
        }

        metrics = EvaluationMetrics()

        for step in range(max_steps):  # noqa: B007
            # Get action from template agent
            action = agent.get_action(
                env.robot_x,
                env.robot_y,
                env.robot_direction,
                obstacle_coords,
            )

            # Track action types
            if action == 0:  # Move forward
                metrics.move_count += 1
            elif action in [1, 2]:  # Turn
                metrics.turn_count += 1
            elif action == 3:  # Patrol
                metrics.patrol_count += 1

            # Execute action
            _obs, reward, terminated, truncated, info = env.step(action)
            metrics.total_reward += float(reward)

            # Track battery
            battery = info.get("battery_percentage", 100.0)
            metrics.min_battery = min(metrics.min_battery, battery)
            if info.get("is_charging", False):
                metrics.charging_events += 1

            # Check for episode end
            if terminated or truncated:
                if battery <= 0:
                    metrics.battery_deaths += 1
                break

        # Calculate final coverage
        total_cells = env.width * env.height - len(obstacle_coords)
        patrolled_cells = sum(
            1 for x in range(env.width) for y in range(env.height)
            if env.last_patrolled[x][y] > 0 and (x, y) not in obstacle_coords
        )
        metrics.coverage_ratio = patrolled_cells / total_cells if total_cells > 0 else 0.0
        metrics.episode_length = step + 1

        result.metrics.append(metrics)

    return result


def compare_agents(
    agents: dict[str, BaseTemplateAgent],
    *,
    width: int = 10,
    height: int = 10,
    episodes: int = 10,
    max_steps: int = 1000,
    seed: int | None = None,
) -> dict[str, ComparisonResult]:
    """
    Compare multiple template agents on the same environment.

    Args:
        agents: Dictionary mapping agent names to agent instances
        width: Environment width
        height: Environment height
        episodes: Number of episodes per agent
        max_steps: Maximum steps per episode
        seed: Random seed for reproducibility

    Returns:
        Dictionary mapping agent names to their evaluation results
    """
    env = SecurityEnvironment(width=width, height=height)
    results = {}

    for name, agent in agents.items():
        results[name] = evaluate_template_agent(
            agent,
            env,
            episodes=episodes,
            max_steps=max_steps,
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
        lines.extend([
            f"Rank #{rank}: {result.agent_name}",
            "-" * 40,
            f"  Average Reward:       {result.avg_reward:>10.2f} (+/- {result.std_reward:.2f})",
            f"  Average Coverage:     {result.avg_coverage:>10.2%}",
            f"  Average Episode Len:  {result.avg_episode_length:>10.1f}",
            f"  Average Patrol Count: {result.avg_patrol_count:>10.1f}",
            f"  Average Min Battery:  {result.avg_min_battery:>10.1f}%",
            f"  Battery Deaths:       {result.total_battery_deaths:>10d}",
            "",
        ])

    lines.extend([
        "=" * 60,
        "Summary",
        "=" * 60,
    ])

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
    max_steps: int = 500,
    seed: int | None = 42,
    include_random: bool = True,
) -> tuple[dict[str, ComparisonResult], str]:
    """
    Run a benchmark comparison of all template agents.

    Args:
        width: Environment width
        height: Environment height
        episodes: Number of episodes per agent
        max_steps: Maximum steps per episode
        seed: Random seed for reproducibility
        include_random: Whether to include RandomWalkAgent

    Returns:
        Tuple of (results dictionary, formatted report string)
    """
    from rl.agents.template_agents import (HorizontalScanAgent,
                                           RandomWalkAgent, SpiralAgent,
                                           VerticalScanAgent)

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
