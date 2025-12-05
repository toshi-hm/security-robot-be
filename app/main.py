from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.api.v1.api import api_router
from app.core.config import settings
from app.core.websocket.manager import websocket_manager
from app.db.database import database_engine
from app.models import Base


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
  async with database_engine.begin() as conn:
    await conn.run_sync(Base.metadata.create_all)
  websocket_manager.start()
  try:
    yield
  finally:
    websocket_manager.stop()


def create_app() -> FastAPI:
  app = FastAPI(title="Security Robot RL API", lifespan=lifespan)

  app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
  )
  app.add_middleware(GZipMiddleware, minimum_size=1000)

  app.include_router(api_router, prefix=settings.api_prefix)
  return app


app = create_app()
