from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.database import database_engine


async_session = async_sessionmaker(database_engine, expire_on_commit=False, class_=AsyncSession)


def get_session() -> AsyncIterator[AsyncSession]:
  return async_session()
