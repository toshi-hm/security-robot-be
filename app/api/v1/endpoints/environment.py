from __future__ import annotations

from app.core.environment.schemas import (EnvironmentDefinition,
                                          EnvironmentState)
from app.core.environment.service import environment_service
from app.schemas.environment import (EnvironmentActionRequest,
                                     EnvironmentSessionCreate,
                                     EnvironmentSessionResetRequest,
                                     EnvironmentSessionState,
                                     EnvironmentStepResponse)
from fastapi import APIRouter, Body, HTTPException, Response, status

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


@router.post(
    "/sessions",
    response_model=dict[str, EnvironmentSessionState],
    status_code=status.HTTP_201_CREATED,
)
async def create_environment_session(
    payload: EnvironmentSessionCreate,
) -> dict[str, EnvironmentSessionState]:
    try:
        session_id, state = await environment_service.create_session(
            payload.environment_id,
            seed=payload.seed,
            config=payload.config,
        )
    except KeyError as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"Environment {payload.environment_id} not found",
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Environment session capacity exceeded. Please try again later.",
        ) from exc

    envelope = EnvironmentSessionState(
        session_id=session_id,
        environment_id=state.environment_id,
        state=state,
    )
    return {"data": envelope}


@router.post(
    "/sessions/{session_id}/reset",
    response_model=dict[str, EnvironmentSessionState],
)
async def reset_environment_session(
    session_id: str,
    payload: EnvironmentSessionResetRequest | None = Body(default=None),
) -> dict[str, EnvironmentSessionState]:
    seed = payload.seed if payload else None

    try:
        state = await environment_service.reset_session(session_id, seed=seed)
    except KeyError as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"Environment session {session_id} not found",
        ) from exc

    envelope = EnvironmentSessionState(
        session_id=session_id,
        environment_id=state.environment_id,
        state=state,
    )
    return {"data": envelope}


@router.post(
    "/sessions/{session_id}/action",
    response_model=dict[str, EnvironmentStepResponse],
)
async def perform_environment_action(
    session_id: str,
    payload: EnvironmentActionRequest,
) -> dict[str, EnvironmentStepResponse]:
    try:
        state, reward, terminated, truncated, info = await environment_service.execute_action(
            session_id,
            payload.action,
        )
    except KeyError as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"Environment session {session_id} not found",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    envelope = EnvironmentStepResponse(
        session_id=session_id,
        environment_id=state.environment_id,
        state=state,
        reward=reward,
        terminated=terminated,
        truncated=truncated,
        info=info,
    )
    return {"data": envelope}


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def close_environment_session(session_id: str) -> Response:
    try:
        await environment_service.close_session(session_id)
    except KeyError as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"Environment session {session_id} not found",
        ) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)
