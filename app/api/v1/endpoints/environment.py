from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db

router = APIRouter()


@router.get('/definitions')
async def list_environments(db: AsyncSession = Depends(get_db)):
  return {'data': []}


@router.get('/definitions/{environment_id}/state')
async def get_environment_state(environment_id: str, db: AsyncSession = Depends(get_db)):
  return {'data': {'environment_id': environment_id}}
