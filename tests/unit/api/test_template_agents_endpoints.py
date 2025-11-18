"""Unit tests for template agents API endpoints."""

from __future__ import annotations

import pytest

from app.api.v1.endpoints import template_agents as template_agents_module
from app.schemas.template_agents import (
    TemplateAgentCompareRequest,
    TemplateAgentExecuteRequest,
    TemplateAgentType,
)


class TestListAgentTypes:
    """Tests for GET /template-agents/types endpoint."""

    def test_returns_all_agent_types(self) -> None:
        """Test that all agent types are returned."""
        result = template_agents_module.list_agent_types()

        assert len(result) == 4
        types = {item["type"] for item in result}
        assert types == {"horizontal_scan", "vertical_scan", "spiral", "random_walk"}

    def test_includes_names_and_descriptions(self) -> None:
        """Test that each type includes name and description."""
        result = template_agents_module.list_agent_types()

        for item in result:
            assert "type" in item
            assert "name" in item
            assert "description" in item
            assert isinstance(item["type"], str)
            assert isinstance(item["name"], str)
            assert isinstance(item["description"], str)

    def test_horizontal_scan_type(self) -> None:
        """Test horizontal scan agent type information."""
        result = template_agents_module.list_agent_types()

        horizontal = next(
            (item for item in result if item["type"] == "horizontal_scan"), None
        )
        assert horizontal is not None
        assert horizontal["name"] == "HorizontalScanAgent"
        assert "ジグザグ" in horizontal["description"]

    def test_spiral_type(self) -> None:
        """Test spiral agent type information."""
        result = template_agents_module.list_agent_types()

        spiral = next((item for item in result if item["type"] == "spiral"), None)
        assert spiral is not None
        assert spiral["name"] == "SpiralAgent"
        assert "時計回り" in spiral["description"]


class TestExecuteAgent:
    """Tests for POST /template-agents/execute endpoint."""

    def test_execute_horizontal_scan_agent(self) -> None:
        """Test executing horizontal scan agent."""
        request = TemplateAgentExecuteRequest(
            agent_type=TemplateAgentType.HORIZONTAL_SCAN,
            width=5,
            height=5,
            episodes=2,
            max_steps=100,
            seed=42,
        )

        response = template_agents_module.execute_agent(request)

        assert response.agent_type == TemplateAgentType.HORIZONTAL_SCAN
        assert response.agent_name == "HorizontalScanAgent"
        assert response.environment == {"width": 5, "height": 5}
        assert response.episodes == 2
        assert len(response.episode_metrics) == 2

    def test_execute_vertical_scan_agent(self) -> None:
        """Test executing vertical scan agent."""
        request = TemplateAgentExecuteRequest(
            agent_type=TemplateAgentType.VERTICAL_SCAN,
            width=6,
            height=4,
            episodes=1,
            max_steps=50,
        )

        response = template_agents_module.execute_agent(request)

        assert response.agent_type == TemplateAgentType.VERTICAL_SCAN
        assert response.agent_name == "VerticalScanAgent"
        assert response.environment == {"width": 6, "height": 4}

    def test_execute_spiral_agent(self) -> None:
        """Test executing spiral agent."""
        request = TemplateAgentExecuteRequest(
            agent_type=TemplateAgentType.SPIRAL,
            width=4,
            height=4,
            episodes=3,
            max_steps=200,
            seed=123,
        )

        response = template_agents_module.execute_agent(request)

        assert response.agent_type == TemplateAgentType.SPIRAL
        assert response.agent_name == "SpiralAgent"
        assert response.episodes == 3

    def test_execute_random_walk_agent(self) -> None:
        """Test executing random walk agent."""
        request = TemplateAgentExecuteRequest(
            agent_type=TemplateAgentType.RANDOM_WALK,
            width=5,
            height=5,
            episodes=2,
            max_steps=100,
            seed=42,
        )

        response = template_agents_module.execute_agent(request)

        assert response.agent_type == TemplateAgentType.RANDOM_WALK
        assert response.agent_name == "RandomWalkAgent"

    def test_response_contains_metrics(self) -> None:
        """Test that response contains all required metrics."""
        request = TemplateAgentExecuteRequest(
            agent_type=TemplateAgentType.HORIZONTAL_SCAN,
            width=5,
            height=5,
            episodes=1,
            max_steps=50,
        )

        response = template_agents_module.execute_agent(request)

        # Check aggregate metrics
        assert isinstance(response.average_reward, float)
        assert isinstance(response.std_reward, float)
        assert response.std_reward >= 0.0
        assert isinstance(response.average_coverage, float)
        assert response.average_coverage >= 0.0
        assert isinstance(response.average_episode_length, float)
        assert response.average_episode_length > 0
        assert isinstance(response.average_patrol_count, float)
        assert isinstance(response.average_min_battery, float)
        assert 0.0 <= response.average_min_battery <= 100.0
        assert isinstance(response.total_battery_deaths, int)
        assert response.total_battery_deaths >= 0

    def test_episode_metrics_structure(self) -> None:
        """Test that episode metrics have correct structure."""
        request = TemplateAgentExecuteRequest(
            agent_type=TemplateAgentType.SPIRAL,
            width=4,
            height=4,
            episodes=2,
            max_steps=100,
        )

        response = template_agents_module.execute_agent(request)

        assert len(response.episode_metrics) == 2

        for i, metrics in enumerate(response.episode_metrics):
            assert metrics.episode == i + 1
            assert isinstance(metrics.total_reward, float)
            assert isinstance(metrics.episode_length, int)
            assert metrics.episode_length > 0
            assert isinstance(metrics.coverage_ratio, float)
            assert 0.0 <= metrics.coverage_ratio <= 1.0
            assert isinstance(metrics.patrol_count, int)
            assert metrics.patrol_count >= 0
            assert isinstance(metrics.move_count, int)
            assert metrics.move_count >= 0
            assert isinstance(metrics.turn_count, int)
            assert metrics.turn_count >= 0
            assert isinstance(metrics.min_battery, float)
            assert 0.0 <= metrics.min_battery <= 100.0
            assert isinstance(metrics.battery_deaths, int)
            assert metrics.battery_deaths >= 0
            assert isinstance(metrics.charging_events, int)
            assert metrics.charging_events >= 0

    def test_small_environment(self) -> None:
        """Test execution on minimum size environment."""
        request = TemplateAgentExecuteRequest(
            agent_type=TemplateAgentType.HORIZONTAL_SCAN,
            width=3,
            height=3,
            episodes=1,
            max_steps=50,
        )

        response = template_agents_module.execute_agent(request)

        assert response.environment == {"width": 3, "height": 3}
        assert len(response.episode_metrics) == 1

    def test_large_environment(self) -> None:
        """Test execution on larger environment."""
        request = TemplateAgentExecuteRequest(
            agent_type=TemplateAgentType.VERTICAL_SCAN,
            width=20,
            height=15,
            episodes=1,
            max_steps=100,
        )

        response = template_agents_module.execute_agent(request)

        assert response.environment == {"width": 20, "height": 15}

    def test_seed_affects_results(self) -> None:
        """Test that different seeds produce different results for random agent."""
        request1 = TemplateAgentExecuteRequest(
            agent_type=TemplateAgentType.RANDOM_WALK,
            width=5,
            height=5,
            episodes=5,
            max_steps=200,
            seed=100,
        )
        request2 = TemplateAgentExecuteRequest(
            agent_type=TemplateAgentType.RANDOM_WALK,
            width=5,
            height=5,
            episodes=5,
            max_steps=200,
            seed=200,
        )

        response1 = template_agents_module.execute_agent(request1)
        response2 = template_agents_module.execute_agent(request2)

        # Results should differ (very unlikely to be the same)
        assert (
            response1.average_reward != response2.average_reward
            or response1.average_coverage != response2.average_coverage
        )


class TestCompareAgents:
    """Tests for POST /template-agents/compare endpoint."""

    def test_compare_two_agents(self) -> None:
        """Test comparing two agents."""
        request = TemplateAgentCompareRequest(
            agent_types=[
                TemplateAgentType.HORIZONTAL_SCAN,
                TemplateAgentType.SPIRAL,
            ],
            width=5,
            height=5,
            episodes=2,
            max_steps=100,
            seed=42,
        )

        response = template_agents_module.compare_agents(request)

        assert response.environment == {"width": 5, "height": 5}
        assert response.episodes == 2
        assert response.max_steps == 100
        assert len(response.results) == 2
        assert response.best_agent in ["HorizontalScanAgent", "SpiralAgent"]
        assert response.worst_agent in ["HorizontalScanAgent", "SpiralAgent"]

    def test_compare_all_agents(self) -> None:
        """Test comparing all four agent types."""
        request = TemplateAgentCompareRequest(
            agent_types=[
                TemplateAgentType.HORIZONTAL_SCAN,
                TemplateAgentType.VERTICAL_SCAN,
                TemplateAgentType.SPIRAL,
                TemplateAgentType.RANDOM_WALK,
            ],
            width=5,
            height=5,
            episodes=1,
            max_steps=50,
        )

        response = template_agents_module.compare_agents(request)

        assert len(response.results) == 4
        agent_names = {r.agent_name for r in response.results}
        assert agent_names == {
            "HorizontalScanAgent",
            "VerticalScanAgent",
            "SpiralAgent",
            "RandomWalkAgent",
        }

    def test_results_sorted_by_reward(self) -> None:
        """Test that results are sorted by average reward (descending)."""
        request = TemplateAgentCompareRequest(
            agent_types=[
                TemplateAgentType.HORIZONTAL_SCAN,
                TemplateAgentType.SPIRAL,
            ],
            width=5,
            height=5,
            episodes=3,
            max_steps=100,
        )

        response = template_agents_module.compare_agents(request)

        # Check ranking
        assert response.results[0].rank == 1
        assert response.results[1].rank == 2
        assert response.results[0].average_reward >= response.results[1].average_reward

    def test_performance_gap_calculation(self) -> None:
        """Test that performance gap is calculated correctly."""
        request = TemplateAgentCompareRequest(
            agent_types=[
                TemplateAgentType.HORIZONTAL_SCAN,
                TemplateAgentType.RANDOM_WALK,
            ],
            width=5,
            height=5,
            episodes=2,
            max_steps=100,
        )

        response = template_agents_module.compare_agents(request)

        expected_gap = (
            response.results[0].average_reward - response.results[-1].average_reward
        )
        assert response.performance_gap == pytest.approx(expected_gap)
        assert response.performance_gap >= 0.0

    def test_comparison_summary_structure(self) -> None:
        """Test that comparison summary has correct structure."""
        request = TemplateAgentCompareRequest(
            agent_types=[TemplateAgentType.SPIRAL],
            width=4,
            height=4,
            episodes=2,
            max_steps=50,
        )

        response = template_agents_module.compare_agents(request)

        assert len(response.results) == 1
        summary = response.results[0]

        assert summary.agent_type == TemplateAgentType.SPIRAL
        assert summary.agent_name == "SpiralAgent"
        assert summary.rank == 1
        assert isinstance(summary.average_reward, float)
        assert isinstance(summary.std_reward, float)
        assert summary.std_reward >= 0.0
        assert isinstance(summary.average_coverage, float)
        assert 0.0 <= summary.average_coverage <= 1.0
        assert isinstance(summary.average_episode_length, float)
        assert summary.average_episode_length > 0
        assert isinstance(summary.average_patrol_count, float)
        assert summary.average_patrol_count >= 0.0
        assert isinstance(summary.average_min_battery, float)
        assert 0.0 <= summary.average_min_battery <= 100.0
        assert isinstance(summary.total_battery_deaths, int)
        assert summary.total_battery_deaths >= 0

    def test_best_and_worst_agent_names(self) -> None:
        """Test that best and worst agent names are set correctly."""
        request = TemplateAgentCompareRequest(
            agent_types=[
                TemplateAgentType.HORIZONTAL_SCAN,
                TemplateAgentType.VERTICAL_SCAN,
            ],
            width=5,
            height=5,
            episodes=1,
            max_steps=50,
        )

        response = template_agents_module.compare_agents(request)

        assert response.best_agent == response.results[0].agent_name
        assert response.worst_agent == response.results[-1].agent_name

    def test_compare_with_different_environment_sizes(self) -> None:
        """Test comparison with different environment sizes."""
        request = TemplateAgentCompareRequest(
            agent_types=[TemplateAgentType.HORIZONTAL_SCAN],
            width=10,
            height=8,
            episodes=1,
            max_steps=50,
        )

        response = template_agents_module.compare_agents(request)

        assert response.environment == {"width": 10, "height": 8}
