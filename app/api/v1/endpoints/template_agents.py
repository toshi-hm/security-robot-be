"""API endpoints for template agent execution and comparison."""

from app.schemas.template_agents import (
    TemplateAgentCompareRequest,
    TemplateAgentCompareResponse,
    TemplateAgentExecuteRequest,
    TemplateAgentExecuteResponse,
    TemplateAgentType,
)
from app.services.template_agent_service import (
    compare_template_agents,
    execute_template_agent,
)
from fastapi import APIRouter

router = APIRouter(prefix="/template-agents", tags=["template-agents"])


@router.get("/types", response_model=list[dict])
def list_agent_types() -> list[dict]:
    """
    List all available template agent types.

    Returns a list of agent types with their descriptions.
    """
    return [
        {
            "type": TemplateAgentType.HORIZONTAL_SCAN.value,
            "name": "HorizontalScanAgent",
            "description": "Scans horizontally row by row in a zigzag pattern",
        },
        {
            "type": TemplateAgentType.VERTICAL_SCAN.value,
            "name": "VerticalScanAgent",
            "description": "Scans vertically column by column in a zigzag pattern",
        },
        {
            "type": TemplateAgentType.SPIRAL.value,
            "name": "SpiralAgent",
            "description": "Spirals inward from outside to center in clockwise direction",
        },
        {
            "type": TemplateAgentType.RANDOM_WALK.value,
            "name": "RandomWalkAgent",
            "description": "Performs random walk (baseline for comparison)",
        },
    ]


@router.post("/execute", response_model=TemplateAgentExecuteResponse)
def execute_agent(request: TemplateAgentExecuteRequest) -> TemplateAgentExecuteResponse:
    """
    Execute a single template agent and return performance metrics.

    This endpoint runs the specified template agent in the security environment
    for the given number of episodes and returns detailed performance metrics.

    The agent will follow its predetermined patrol pattern, and metrics such as
    coverage ratio, battery management, and rewards will be tracked.
    """
    return execute_template_agent(request)


@router.post("/compare", response_model=TemplateAgentCompareResponse)
def compare_agents(request: TemplateAgentCompareRequest) -> TemplateAgentCompareResponse:
    """
    Compare multiple template agents on the same environment.

    This endpoint evaluates multiple template agents on the same environment
    configuration and returns a ranked comparison of their performance.

    Results are sorted by average reward, with the best performing agent ranked first.
    """
    return compare_template_agents(request)
