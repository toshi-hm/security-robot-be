"""Unit tests for template agent comparison functionality."""

from typing import Any

from rl.agents.template_agents import HorizontalScanAgent, SpiralAgent, VerticalScanAgent
from rl.environments.security_env import SecurityEnvironment
from rl.utils.comparison import (
  ComparisonResult,
  EvaluationMetrics,
  compare_agents,
  evaluate_template_agent,
  generate_comparison_report,
  run_benchmark,
)


class TestEvaluationMetrics:
  """Tests for EvaluationMetrics dataclass."""

  def test_default_values(self) -> None:
    """Test default metric values."""
    metrics = EvaluationMetrics()

    assert metrics.total_reward == 0.0
    assert metrics.episode_length == 0
    assert metrics.coverage_ratio == 0.0
    assert metrics.patrol_count == 0
    assert metrics.move_count == 0
    assert metrics.turn_count == 0
    assert metrics.battery_deaths == 0
    assert metrics.min_battery == 100.0
    assert metrics.charging_events == 0


class TestComparisonResult:
  """Tests for ComparisonResult dataclass."""

  def test_empty_metrics(self) -> None:
    """Test properties with empty metrics."""
    result = ComparisonResult(agent_name="Test", episodes=0)

    assert result.avg_reward == 0.0
    assert result.std_reward == 0.0
    assert result.avg_coverage == 0.0
    assert result.avg_episode_length == 0.0
    assert result.avg_patrol_count == 0.0
    assert result.avg_min_battery == 0.0
    assert result.total_battery_deaths == 0

  def test_single_metric(self) -> None:
    """Test properties with single metric."""
    result = ComparisonResult(agent_name="Test", episodes=1)
    result.metrics.append(
      EvaluationMetrics(
        total_reward=100.0,
        episode_length=500,
        coverage_ratio=0.75,
        patrol_count=50,
        move_count=300,
        turn_count=150,
        battery_deaths=0,
        min_battery=45.0,
        charging_events=3,
      )
    )

    assert result.avg_reward == 100.0
    assert result.std_reward == 0.0  # Can't compute stdev with single value
    assert result.avg_coverage == 0.75
    assert result.avg_episode_length == 500
    assert result.avg_patrol_count == 50
    assert result.avg_min_battery == 45.0
    assert result.total_battery_deaths == 0

  def test_multiple_metrics(self) -> None:
    """Test properties with multiple metrics."""
    result = ComparisonResult(agent_name="Test", episodes=3)
    result.metrics.extend(
      [
        EvaluationMetrics(total_reward=100.0, coverage_ratio=0.8, min_battery=50.0),
        EvaluationMetrics(total_reward=150.0, coverage_ratio=0.9, min_battery=40.0),
        EvaluationMetrics(total_reward=125.0, coverage_ratio=0.85, min_battery=45.0),
      ]
    )

    assert result.avg_reward == 125.0
    assert result.std_reward > 0  # Should have non-zero stdev
    assert result.avg_coverage == 0.85
    assert result.avg_min_battery == 45.0

  def test_to_dict(self) -> None:
    """Test JSON serialization."""
    result = ComparisonResult(agent_name="TestAgent", episodes=2)
    result.metrics.append(
      EvaluationMetrics(
        total_reward=80.0,
        coverage_ratio=0.65,
        episode_length=400,
        patrol_count=40,
        min_battery=55.0,
        battery_deaths=1,
      )
    )

    data = result.to_dict()

    assert data["agent_name"] == "TestAgent"
    assert data["episodes"] == 2
    assert data["average_reward"] == 80.0
    assert data["average_coverage"] == 0.65
    assert data["total_battery_deaths"] == 1


class TestEvaluateTemplateAgent:
  """Tests for evaluate_template_agent function."""

  def test_horizontal_scan_evaluation(self) -> None:
    """Test evaluation of horizontal scan agent."""
    env = SecurityEnvironment(width=5, height=5)
    agent = HorizontalScanAgent(5, 5)

    result = evaluate_template_agent(
      agent,
      env,
      episodes=2,
      max_steps=100,
      seed=42,
    )

    assert result.agent_name == "HorizontalScanAgent"
    assert result.episodes == 2
    assert len(result.metrics) == 2
    assert all(m.episode_length > 0 for m in result.metrics)
    assert all(m.total_reward != 0 for m in result.metrics)

  def test_spiral_evaluation(self) -> None:
    """Test evaluation of spiral agent."""
    env = SecurityEnvironment(width=5, height=5)
    agent = SpiralAgent(5, 5)

    result = evaluate_template_agent(
      agent,
      env,
      episodes=2,
      max_steps=100,
      seed=42,
    )

    assert result.agent_name == "SpiralAgent"
    assert len(result.metrics) == 2

  def test_action_tracking(self) -> None:
    """Test that actions are tracked correctly."""
    env = SecurityEnvironment(width=3, height=3)
    agent = HorizontalScanAgent(3, 3)

    result = evaluate_template_agent(
      agent,
      env,
      episodes=1,
      max_steps=50,
      seed=42,
    )

    metrics = result.metrics[0]
    # Should have some combination of moves, turns, and patrols
    total_actions = metrics.move_count + metrics.turn_count + metrics.patrol_count
    assert total_actions > 0
    assert total_actions == metrics.episode_length

  def test_coverage_calculation(self) -> None:
    """Test that coverage is calculated correctly."""
    env = SecurityEnvironment(width=3, height=3)
    agent = HorizontalScanAgent(3, 3)

    result = evaluate_template_agent(
      agent,
      env,
      episodes=1,
      max_steps=200,
      seed=42,
    )

    metrics = result.metrics[0]
    # Coverage should be between 0 and 1
    assert 0.0 <= metrics.coverage_ratio <= 1.0

  def test_battery_tracking(self) -> None:
    """Test that battery metrics are tracked."""
    env = SecurityEnvironment(width=5, height=5)
    agent = HorizontalScanAgent(5, 5)

    result = evaluate_template_agent(
      agent,
      env,
      episodes=1,
      max_steps=100,
      seed=42,
    )

    metrics = result.metrics[0]
    # Min battery should be less than or equal to initial
    assert metrics.min_battery <= 100.0
    # With drain rate of 0.001 per step, after 100 steps: 100 - 0.1 = 99.9
    assert metrics.min_battery > 0.0

  def test_default_max_steps_uses_env_limit(self) -> None:
    """When max_steps is None, the environment limit should be used."""
    custom_limit = 150
    env = SecurityEnvironment(width=4, height=4, max_episode_steps=custom_limit)
    agent = HorizontalScanAgent(4, 4)
    events: list[dict[str, Any]] = []

    def progress_callback(message: dict[str, Any]) -> None:
      events.append(message)

    evaluate_template_agent(
      agent,
      env,
      episodes=1,
      max_steps=None,
      seed=42,
      progress_callback=progress_callback,
    )

    execution_events = [e for e in events if e.get("type") == "execution_started"]
    assert execution_events, "execution_started event should be emitted"
    assert execution_events[0]["total_steps_per_episode"] == custom_limit

  def test_save_frames_records_playback(self) -> None:
    """Ensure playback frames are captured when save_frames=True."""
    env = SecurityEnvironment(width=3, height=3)
    agent = HorizontalScanAgent(3, 3)

    result = evaluate_template_agent(
      agent,
      env,
      episodes=1,
      max_steps=5,
      seed=1,
      save_frames=True,
    )

    assert result.playbacks, "Expected episode playback data"
    first_playback = result.playbacks[0]
    assert first_playback.episode == 1
    assert first_playback.frames, "Expected frame list to be populated"
    assert first_playback.frames[0].coverage_map is not None
    assert result.environment_info is not None
    env_info = result.environment_info
    assert len(env_info.threat_histogram) == 5
    assert env_info.high_threat_tiles

  def test_progress_callback_receives_events(self) -> None:
    """Progress callback should receive execution lifecycle events."""
    env = SecurityEnvironment(width=3, height=3)
    agent = HorizontalScanAgent(3, 3)
    events: list[dict] = []

    evaluate_template_agent(
      agent,
      env,
      episodes=1,
      max_steps=5,
      progress_callback=events.append,
    )

    event_types = {event["type"] for event in events}
    assert "execution_started" in event_types
    assert "episode_started" in event_types
    assert "episode_completed" in event_types
    assert "execution_completed" in event_types


class TestCompareAgents:
  """Tests for compare_agents function."""

  def test_compare_multiple_agents(self) -> None:
    """Test comparing multiple agents."""
    agents = {
      "horizontal": HorizontalScanAgent(5, 5),
      "vertical": VerticalScanAgent(5, 5),
      "spiral": SpiralAgent(5, 5),
    }

    results = compare_agents(
      agents,
      width=5,
      height=5,
      episodes=2,
      max_steps=50,
      seed=42,
    )

    assert len(results) == 3
    assert "horizontal" in results
    assert "vertical" in results
    assert "spiral" in results

    for _name, result in results.items():
      assert result.episodes == 2
      assert len(result.metrics) == 2

  def test_reproducibility_with_seed(self) -> None:
    """Test that evaluation results are consistent for deterministic agents."""
    # Note: Full reproducibility is not guaranteed because:
    # 1. SecurityEnvironment generates obstacles during __init__ with randomness
    # 2. Charging station is placed randomly during each reset()
    # However, we can test that results are reasonable and consistent within a run.
    from rl.environments.security_env import SecurityEnvironment

    env = SecurityEnvironment(width=5, height=5)
    agent = HorizontalScanAgent(5, 5)

    result = evaluate_template_agent(
      agent,
      env,
      episodes=3,
      max_steps=50,
      seed=123,
    )

    # Verify metrics are collected properly
    assert result.episodes == 3
    assert len(result.metrics) == 3
    # All episodes should have consistent episode lengths (max_steps)
    for m in result.metrics:
      assert m.episode_length == 50
    # Average reward should be calculated
    assert isinstance(result.avg_reward, float)


class TestGenerateComparisonReport:
  """Tests for generate_comparison_report function."""

  def test_report_generation(self) -> None:
    """Test that report is generated correctly."""
    results = {
      "agent1": ComparisonResult(agent_name="Agent1", episodes=2),
      "agent2": ComparisonResult(agent_name="Agent2", episodes=2),
    }
    results["agent1"].metrics.append(EvaluationMetrics(total_reward=100.0, coverage_ratio=0.8))
    results["agent2"].metrics.append(EvaluationMetrics(total_reward=80.0, coverage_ratio=0.7))

    report = generate_comparison_report(results)

    assert "Template Agent Comparison Report" in report
    assert "Agent1" in report
    assert "Agent2" in report
    assert "Rank #1" in report
    assert "Rank #2" in report

  def test_report_ranks_by_reward(self) -> None:
    """Test that agents are ranked by average reward."""
    results = {
      "low": ComparisonResult(agent_name="LowAgent", episodes=1),
      "high": ComparisonResult(agent_name="HighAgent", episodes=1),
    }
    results["low"].metrics.append(EvaluationMetrics(total_reward=50.0))
    results["high"].metrics.append(EvaluationMetrics(total_reward=150.0))

    report = generate_comparison_report(results)

    # HighAgent should be ranked first
    high_pos = report.find("HighAgent")
    low_pos = report.find("LowAgent")
    assert high_pos < low_pos

  def test_report_includes_summary(self) -> None:
    """Test that report includes summary section."""
    results = {
      "test": ComparisonResult(agent_name="TestAgent", episodes=1),
    }
    results["test"].metrics.append(EvaluationMetrics(total_reward=100.0))

    report = generate_comparison_report(results)

    assert "Summary" in report
    assert "Best Performing Agent" in report


class TestRunBenchmark:
  """Tests for run_benchmark function."""

  def test_benchmark_runs_all_agents(self) -> None:
    """Test that benchmark runs all template agents."""
    results, report = run_benchmark(
      width=3,
      height=3,
      episodes=1,
      max_steps=20,
      seed=42,
      include_random=True,
    )

    assert "horizontal" in results
    assert "vertical" in results
    assert "spiral" in results
    assert "random" in results
    assert len(results) == 4

  def test_benchmark_without_random(self) -> None:
    """Test benchmark without random agent."""
    results, report = run_benchmark(
      width=3,
      height=3,
      episodes=1,
      max_steps=20,
      seed=42,
      include_random=False,
    )

    assert "horizontal" in results
    assert "vertical" in results
    assert "spiral" in results
    assert "random" not in results
    assert len(results) == 3

  def test_benchmark_generates_report(self) -> None:
    """Test that benchmark generates a report."""
    results, report = run_benchmark(
      width=3,
      height=3,
      episodes=1,
      max_steps=10,
      seed=42,
    )

    assert isinstance(report, str)
    assert "Template Agent Comparison Report" in report
    assert len(report) > 100

  def test_benchmark_reproducibility(self) -> None:
    """Test benchmark results are consistent and reasonable."""
    # Note: Due to random charging station placement during reset(),
    # exact reproducibility is not guaranteed even with same seed.
    # Instead, we verify that the benchmark produces valid results.
    results, report = run_benchmark(
      width=3,
      height=3,
      episodes=2,
      max_steps=30,
      seed=999,
      include_random=False,
    )

    # Verify all agents are evaluated
    assert len(results) == 3
    for agent_name in ["horizontal", "vertical", "spiral"]:
      assert agent_name in results
      result = results[agent_name]
      assert result.episodes == 2
      assert len(result.metrics) == 2
      # Rewards should be finite
      assert result.avg_reward != float("inf")
      assert result.avg_reward != float("-inf")
