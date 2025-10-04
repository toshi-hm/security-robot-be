from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db

router = APIRouter()


@router.get('/sessions')
async def list_sessions(db: AsyncSession = Depends(get_db)):
  return {'data': []}


@router.post('/sessions')
async def start_session(payload: dict, db: AsyncSession = Depends(get_db)):
  return {'data': payload | {'id': 'session-1'}}


@router.get('/sessions/{session_id}/metrics')
async def get_metrics(session_id: str, db: AsyncSession = Depends(get_db)):
  return {'data': {'session_id': session_id, 'points': []}}
