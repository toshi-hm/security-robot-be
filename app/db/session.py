"""Database session helpers for asynchronous and synchronous contexts."""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Session, sessionmaker

from app.db.database import database_engine


# Async session factory used by FastAPI request handlers.
async_session = async_sessionmaker(database_engine, expire_on_commit=False, class_=AsyncSession)


def get_session() -> AsyncIterator[AsyncSession]:
  return async_session()


# Celery workers operate in a synchronous context.  The async engine exposes a
# synchronous facade that we reuse here to keep both execution models in sync.
SessionLocal = sessionmaker(
  bind=database_engine.sync_engine,
  class_=Session,
  autoflush=False,
  autocommit=False,
  expire_on_commit=False,
)


__all__ = ["async_session", "get_session", "SessionLocal"]
