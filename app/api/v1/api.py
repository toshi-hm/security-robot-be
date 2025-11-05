from fastapi import APIRouter

from app.api.v1.endpoints import (
    environment,
    files,
    health,
    jobs,
    playback,
    training,
    websocket,
)

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(environment.router, prefix="/environment", tags=["environment"])
api_router.include_router(training.router, prefix="/training", tags=["training"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(files.router, prefix="/files", tags=["files"])
api_router.include_router(playback.router, prefix="/playback", tags=["playback"])
api_router.include_router(websocket.router, prefix="/ws", tags=["websocket"])
