from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import logging
import asyncio

router = APIRouter()

active_connections = []

class WebSocketLogHandler(logging.Handler):
    def emit(self, record):
        try:
            log_entry = self.format(record)
            for connection in active_connections:
                # Fire and forget log messages to avoid blocking
                asyncio.create_task(connection.send_text(log_entry))
        except Exception:
            pass

ws_handler = WebSocketLogHandler()
ws_handler.setFormatter(logging.Formatter("%(message)s"))
logging.getLogger().addHandler(ws_handler)

from app.core import config
from fastapi import status

@router.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    # Manual Authentication since Depends(get_api_key) lacks Request
    auth = websocket.headers.get("Authorization")
    if not auth or auth != f"Bearer {config.APP_API_KEY}":
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
        
    global active_connections
    await websocket.accept()

    active_connections.append(websocket)
    try:
        while True:
            # We don't expect messages from client, just keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in active_connections:
            active_connections.remove(websocket)
    except Exception:
        if websocket in active_connections:
            active_connections.remove(websocket)
