from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.core.environment.schemas import EnvironmentDefinition, EnvironmentState
from app.core.environment.service import environment_service

router = APIRouter()


@router.get("/definitions", response_model=dict[str, list[EnvironmentDefinition]])
async def list_environments() -> dict[str, list[EnvironmentDefinition]]:
    definitions = await environment_service.list_definitions()
    return {"data": definitions}


@router.get(
    "/definitions/{environment_id}/state",
    response_model=dict[str, EnvironmentState],
)
async def get_environment_state(environment_id: str) -> dict[str, EnvironmentState]:
    try:
        state = await environment_service.get_state(environment_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Environment {environment_id} not found",
        ) from exc

    return {"data": state}
