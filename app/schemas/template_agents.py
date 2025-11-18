"""Schemas for template agent execution API."""

from enum import Enum

from pydantic import BaseModel, Field


class TemplateAgentType(str, Enum):
    """Available template agent types."""

    HORIZONTAL_SCAN = "horizontal_scan"
    VERTICAL_SCAN = "vertical_scan"
    SPIRAL = "spiral"
    RANDOM_WALK = "random_walk"


class TemplateAgentExecuteRequest(BaseModel):
    """Request schema for executing a template agent."""

    agent_type: TemplateAgentType = Field(
        ...,
        description="Type of template agent to execute",
    )
    width: int = Field(
        default=10,
        ge=3,
        le=100,
        description="Environment grid width",
    )
    height: int = Field(
        default=10,
        ge=3,
        le=100,
        description="Environment grid height",
    )
    episodes: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Number of episodes to run",
    )
    max_steps: int = Field(
        default=1000,
        ge=10,
        le=10000,
        description="Maximum steps per episode",
    )
    seed: int | None = Field(
        default=None,
        description="Random seed for reproducibility",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "agent_type": "horizontal_scan",
                    "width": 10,
                    "height": 10,
                    "episodes": 10,
                    "max_steps": 1000,
                    "seed": 42,
                }
            ]
        }
    }


class TemplateAgentEpisodeMetrics(BaseModel):
    """Metrics for a single episode."""

    episode: int = Field(..., description="Episode number")
    total_reward: float = Field(..., description="Total reward for the episode")
    episode_length: int = Field(..., description="Number of steps in the episode")
    coverage_ratio: float = Field(
        ..., ge=0.0, description="Ratio of patrolled cells"
    )
    patrol_count: int = Field(..., ge=0, description="Number of patrol actions")
    move_count: int = Field(..., ge=0, description="Number of move forward actions")
    turn_count: int = Field(..., ge=0, description="Number of turn actions")
    min_battery: float = Field(..., ge=0.0, le=100.0, description="Minimum battery percentage")
    battery_deaths: int = Field(..., ge=0, description="Number of battery deaths")
    charging_events: int = Field(..., ge=0, description="Number of charging events")


class TemplateAgentExecuteResponse(BaseModel):
    """Response schema for template agent execution."""

    agent_type: TemplateAgentType = Field(
        ...,
        description="Type of template agent executed",
    )
    agent_name: str = Field(
        ...,
        description="Class name of the agent",
    )
    environment: dict = Field(
        ...,
        description="Environment configuration",
    )
    episodes: int = Field(
        ...,
        description="Number of episodes executed",
    )
    average_reward: float = Field(
        ...,
        description="Average total reward across episodes",
    )
    std_reward: float = Field(
        ...,
        ge=0.0,
        description="Standard deviation of rewards",
    )
    average_coverage: float = Field(
        ...,
        ge=0.0,
        description="Average coverage ratio",
    )
    average_episode_length: float = Field(
        ...,
        gt=0,
        description="Average episode length",
    )
    average_patrol_count: float = Field(
        ...,
        ge=0.0,
        description="Average number of patrol actions",
    )
    average_min_battery: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Average minimum battery percentage",
    )
    total_battery_deaths: int = Field(
        ...,
        ge=0,
        description="Total number of battery deaths across all episodes",
    )
    episode_metrics: list[TemplateAgentEpisodeMetrics] = Field(
        ...,
        description="Detailed metrics for each episode",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "agent_type": "horizontal_scan",
                    "agent_name": "HorizontalScanAgent",
                    "environment": {"width": 10, "height": 10},
                    "episodes": 10,
                    "average_reward": 125.5,
                    "std_reward": 15.2,
                    "average_coverage": 0.85,
                    "average_episode_length": 950.0,
                    "average_patrol_count": 80.5,
                    "average_min_battery": 45.0,
                    "total_battery_deaths": 0,
                    "episode_metrics": [
                        {
                            "episode": 1,
                            "total_reward": 120.0,
                            "episode_length": 1000,
                            "coverage_ratio": 0.82,
                            "patrol_count": 78,
                            "move_count": 750,
                            "turn_count": 172,
                            "min_battery": 42.5,
                            "battery_deaths": 0,
                            "charging_events": 3,
                        }
                    ],
                }
            ]
        }
    }


class TemplateAgentCompareRequest(BaseModel):
    """Request schema for comparing multiple template agents."""

    agent_types: list[TemplateAgentType] = Field(
        default=[
            TemplateAgentType.HORIZONTAL_SCAN,
            TemplateAgentType.VERTICAL_SCAN,
            TemplateAgentType.SPIRAL,
        ],
        min_length=1,
        max_length=4,
        description="List of agent types to compare",
    )
    width: int = Field(
        default=10,
        ge=3,
        le=100,
        description="Environment grid width",
    )
    height: int = Field(
        default=10,
        ge=3,
        le=100,
        description="Environment grid height",
    )
    episodes: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Number of episodes per agent",
    )
    max_steps: int = Field(
        default=1000,
        ge=10,
        le=10000,
        description="Maximum steps per episode",
    )
    seed: int | None = Field(
        default=None,
        description="Random seed for reproducibility",
    )


class TemplateAgentComparisonSummary(BaseModel):
    """Summary of a single agent's performance in comparison."""

    agent_type: TemplateAgentType = Field(..., description="Type of agent")
    agent_name: str = Field(..., description="Class name of the agent")
    rank: int = Field(..., ge=1, description="Rank by average reward")
    average_reward: float = Field(..., description="Average total reward")
    std_reward: float = Field(..., ge=0.0, description="Standard deviation of rewards")
    average_coverage: float = Field(..., ge=0.0, description="Average coverage ratio")
    average_episode_length: float = Field(..., gt=0, description="Average episode length")
    average_patrol_count: float = Field(..., ge=0.0, description="Average patrol count")
    average_min_battery: float = Field(..., ge=0.0, le=100.0, description="Average minimum battery")
    total_battery_deaths: int = Field(..., ge=0, description="Total battery deaths")


class TemplateAgentCompareResponse(BaseModel):
    """Response schema for comparing multiple template agents."""

    environment: dict = Field(..., description="Environment configuration")
    episodes: int = Field(..., description="Number of episodes per agent")
    max_steps: int = Field(..., description="Maximum steps per episode")
    results: list[TemplateAgentComparisonSummary] = Field(
        ...,
        description="Comparison results sorted by rank",
    )
    best_agent: str = Field(..., description="Name of the best performing agent")
    worst_agent: str = Field(..., description="Name of the worst performing agent")
    performance_gap: float = Field(
        ...,
        description="Difference in average reward between best and worst",
    )
