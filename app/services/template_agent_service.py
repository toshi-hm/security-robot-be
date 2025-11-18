"""Service for executing and comparing template agents."""

from app.schemas.template_agents import (
  TemplateAgentCompareRequest,
  TemplateAgentCompareResponse,
  TemplateAgentComparisonSummary,
  TemplateAgentEpisodeMetrics,
  TemplateAgentExecuteRequest,
  TemplateAgentExecuteResponse,
  TemplateAgentType,
)
from rl.agents.template_agents import (
  BaseTemplateAgent,
  HorizontalScanAgent,
  RandomWalkAgent,
  SpiralAgent,
  VerticalScanAgent,
)
from rl.environments.security_env import SecurityEnvironment
from rl.utils.comparison import evaluate_template_agent


def _create_agent(
  agent_type: TemplateAgentType, width: int, height: int, seed: int | None = None
) -> BaseTemplateAgent:
  """Create a template agent instance based on type."""
  if agent_type == TemplateAgentType.HORIZONTAL_SCAN:
    return HorizontalScanAgent(width, height)
  elif agent_type == TemplateAgentType.VERTICAL_SCAN:
    return VerticalScanAgent(width, height)
  elif agent_type == TemplateAgentType.SPIRAL:
    return SpiralAgent(width, height)
  elif agent_type == TemplateAgentType.RANDOM_WALK:
    return RandomWalkAgent(width, height, seed=seed)
  else:
    raise ValueError(f"Unknown agent type: {agent_type}")


def execute_template_agent(
  request: TemplateAgentExecuteRequest,
) -> TemplateAgentExecuteResponse:
  """
  Execute a template agent and return performance metrics.

  Args:
      request: Request containing agent type and execution parameters

  Returns:
      Response with execution results and metrics
  """
  # Create environment and agent
  env = SecurityEnvironment(width=request.width, height=request.height)
  agent = _create_agent(request.agent_type, request.width, request.height, request.seed)

  # Run evaluation
  result = evaluate_template_agent(
    agent,
    env,
    episodes=request.episodes,
    max_steps=request.max_steps,
    seed=request.seed,
  )

  # Convert metrics to response format
  episode_metrics = []
  for i, m in enumerate(result.metrics):
    episode_metrics.append(
      TemplateAgentEpisodeMetrics(
        episode=i + 1,
        total_reward=m.total_reward,
        episode_length=m.episode_length,
        coverage_ratio=m.coverage_ratio,
        patrol_count=m.patrol_count,
        move_count=m.move_count,
        turn_count=m.turn_count,
        min_battery=m.min_battery,
        battery_deaths=m.battery_deaths,
        charging_events=m.charging_events,
      )
    )

  return TemplateAgentExecuteResponse(
    agent_type=request.agent_type,
    agent_name=result.agent_name,
    environment={"width": request.width, "height": request.height},
    episodes=result.episodes,
    average_reward=result.avg_reward,
    std_reward=result.std_reward,
    average_coverage=result.avg_coverage,
    average_episode_length=result.avg_episode_length,
    average_patrol_count=result.avg_patrol_count,
    average_min_battery=result.avg_min_battery,
    total_battery_deaths=result.total_battery_deaths,
    episode_metrics=episode_metrics,
  )


def compare_template_agents(
  request: TemplateAgentCompareRequest,
) -> TemplateAgentCompareResponse:
  """
  Compare multiple template agents and return ranked results.

  Args:
      request: Request containing agent types and execution parameters

  Returns:
      Response with comparison results sorted by performance
  """
  # Create shared environment
  env = SecurityEnvironment(width=request.width, height=request.height)

  # Evaluate each agent
  results_list = []
  for agent_type in request.agent_types:
    agent = _create_agent(agent_type, request.width, request.height, request.seed)
    result = evaluate_template_agent(
      agent,
      env,
      episodes=request.episodes,
      max_steps=request.max_steps,
      seed=request.seed,
    )
    results_list.append((agent_type, result))

  # Sort by average reward (descending)
  results_list.sort(key=lambda x: x[1].avg_reward, reverse=True)

  # Create summaries
  summaries = []
  for rank, (agent_type, result) in enumerate(results_list, 1):
    summaries.append(
      TemplateAgentComparisonSummary(
        agent_type=agent_type,
        agent_name=result.agent_name,
        rank=rank,
        average_reward=result.avg_reward,
        std_reward=result.std_reward,
        average_coverage=result.avg_coverage,
        average_episode_length=result.avg_episode_length,
        average_patrol_count=result.avg_patrol_count,
        average_min_battery=result.avg_min_battery,
        total_battery_deaths=result.total_battery_deaths,
      )
    )

  # Calculate performance gap
  best_reward = summaries[0].average_reward if summaries else 0.0
  worst_reward = summaries[-1].average_reward if summaries else 0.0

  return TemplateAgentCompareResponse(
    environment={"width": request.width, "height": request.height},
    episodes=request.episodes,
    max_steps=request.max_steps,
    results=summaries,
    best_agent=summaries[0].agent_name if summaries else "N/A",
    worst_agent=summaries[-1].agent_name if summaries else "N/A",
    performance_gap=best_reward - worst_reward,
  )
