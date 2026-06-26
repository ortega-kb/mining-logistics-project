from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import logging
import json


# Logger 
logger = logging.getLogger(__name__)

# Router 
router = APIRouter()

# WebSocket clients
ws_clients = []

# Accept websocket connections
@router.websocket("/ws/trucks")
async def websocket_manager(websocket: WebSocket):
    await websocket.accept()
    ws_clients.append(websocket)
    logger.info(f"Connected client: {websocket.client}")

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_clients.remove(websocket)
        logger.info(f"Disconnected client: {websocket.client}")


# Publish positions to ws clients 
async def publish_positions(trucks_positions: list):
    if not ws_clients:
        return 

    message = json.dumps(trucks_positions)
    for ws_client in ws_clients:
        await ws_client.send_text(message)
    



