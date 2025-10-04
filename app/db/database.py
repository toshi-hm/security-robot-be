from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core.config import settings


def get_engine() -> AsyncEngine:
  return create_async_engine(settings.database_url, future=True)


database_engine = get_engine()
