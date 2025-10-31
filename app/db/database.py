"""Database engine helpers for asynchronous and synchronous contexts."""

from __future__ import annotations

from typing import Final

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core.config import settings

_SYNC_DRIVER_MAP: Final[dict[tuple[str, str | None], str | None]] = {
  ("postgresql", "asyncpg"): "psycopg",
  ("postgresql", "psycopg_async"): "psycopg",
  ("mysql", "aiomysql"): "pymysql",
  ("sqlite", "aiosqlite"): None,
}


def _resolve_sync_driver(database_url: str) -> URL:
  url = make_url(database_url)
  if "+" not in url.drivername:
    return url

  dialect, async_driver = url.drivername.split("+", 1)
  sync_driver = _SYNC_DRIVER_MAP.get((dialect, async_driver))
  if sync_driver is None:
    return url.set(drivername=dialect)
  if sync_driver:
    return url.set(drivername=f"{dialect}+{sync_driver}")
  return url.set(drivername=dialect)


def get_async_engine() -> AsyncEngine:
  """Create a new asynchronous SQLAlchemy engine instance."""

  return create_async_engine(settings.database_url, future=True)


def get_sync_engine() -> Engine:
  """Create a dedicated synchronous SQLAlchemy engine instance."""

  sync_url = _resolve_sync_driver(settings.database_url)
  return create_engine(sync_url, future=True)


async_engine: AsyncEngine = get_async_engine()
sync_engine: Engine = get_sync_engine()

# Backwards compatibility alias kept for existing imports.  It intentionally
# exposes only the asynchronous engine; synchronous contexts should rely on
# ``sync_engine`` instead of the async facade's ``sync_engine`` attribute.
database_engine = async_engine


__all__ = ["async_engine", "sync_engine", "database_engine", "get_async_engine", "get_sync_engine"]
