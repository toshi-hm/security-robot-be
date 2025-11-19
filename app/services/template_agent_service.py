"""Service for executing and comparing template agents."""

from uuid import uuid4

from app.schemas.template_agents import (
  TemplateAgentCompareRequest,
  TemplateAgentCompareResponse,
  TemplateAgentComparisonSummary,
  TemplateAgentEpisodeMetrics,
  TemplateAgentEpisodePlayback,
  TemplateAgentExecuteRequest,
  TemplateAgentExecuteResponse,
  TemplateAgentFrameData,
  TemplateAgentEnvironmentInfo,
  TemplateAgentExecutionInitResponse,
  TemplateAgentType,
)
from app.services.template_agent_progress import (
  TemplateAgentProgressPublisher,
  template_agent_progress_manager,
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


def generate_execution_id() -> str:
  """Create a new execution identifier for template agent runs."""
  return f"template-agent-{uuid4()}"


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
  execution_id = request.execution_id or generate_execution_id()
  progress_callback = (
    TemplateAgentProgressPublisher(execution_id, template_agent_progress_manager)
    if request.execution_id
    else None
  )

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
    save_frames=request.save_frames,
    progress_callback=progress_callback,
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

  env_info_source = result.environment_info
  if env_info_source is None:
    env_info_source = TemplateAgentEnvironmentInfo(
      width=request.width,
      height=request.height,
      threat_grid=[],
      average_threat_level=0.0,
      max_threat_level=0.0,
      min_threat_level=0.0,
      threat_histogram=[0, 0, 0, 0, 0],
      high_threat_tiles=[],
      obstacles=[],
      charging_station={"x": 0, "y": 0},
      suspicious_objects=[],
    )
  else:
    env_info_source = TemplateAgentEnvironmentInfo(
      width=env_info_source.width,
      height=env_info_source.height,
      threat_grid=env_info_source.threat_grid,
      average_threat_level=env_info_source.average_threat_level,
      max_threat_level=env_info_source.max_threat_level,
      min_threat_level=env_info_source.min_threat_level,
      threat_histogram=env_info_source.threat_histogram,
      high_threat_tiles=env_info_source.high_threat_tiles,
      obstacles=env_info_source.obstacles,
      charging_station=env_info_source.charging_station,
      suspicious_objects=env_info_source.suspicious_objects,
    )

  episode_playbacks: list[TemplateAgentEpisodePlayback] = []
  if request.save_frames:
    for playback in result.playbacks:
      frames = [
        TemplateAgentFrameData(
          timestep=frame.timestep,
          robot_x=frame.robot_x,
          robot_y=frame.robot_y,
          robot_orientation=frame.robot_orientation,
          action=frame.action,
          reward=frame.reward,
          battery_percentage=frame.battery_percentage,
          is_charging=frame.is_charging,
          coverage_map=frame.coverage_map,
          timestamp=frame.timestamp,
        )
        for frame in playback.frames
      ]
      episode_playbacks.append(
        TemplateAgentEpisodePlayback(
          episode=playback.episode,
          frames=frames,
          total_reward=playback.total_reward,
          final_coverage=playback.final_coverage,
          episode_length=playback.episode_length,
        )
      )

  return TemplateAgentExecuteResponse(
    agent_type=request.agent_type,
    agent_name=result.agent_name,
    execution_id=execution_id,
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
    environment_info=env_info_source,
    episode_playbacks=episode_playbacks,
  )


def initialize_execution() -> TemplateAgentExecutionInitResponse:
  """Generate a server-side execution ID for WebSocket subscriptions."""
  execution_id = generate_execution_id()
  return TemplateAgentExecutionInitResponse(
    execution_id=execution_id,
    websocket_url=f"/api/v1/template-agents/ws/{execution_id}",
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
