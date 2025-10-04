from fastapi import APIRouter, WebSocket

router = APIRouter()


@router.websocket('/training')
async def training_updates(websocket: WebSocket):
  await websocket.accept()
  await websocket.send_json({'event': 'connected'})
  await websocket.close()
