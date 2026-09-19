import json
from datetime import UTC, datetime

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from packages.shared.nexus_shared.logging import get_logger

logger = get_logger("nexus.websocket")
ws_router = APIRouter(tags=["WebSocket"])


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, set[WebSocket]] = {
            "dashboard": set(),
            "ambient": set(),
        }

    async def connect(self, websocket: WebSocket, surface: str):
        await websocket.accept()
        if surface not in self.active_connections:
            self.active_connections[surface] = set()
        self.active_connections[surface].add(websocket)
        logger.info(
            "websocket_client_connected",
            surface=surface,
            total=len(self.active_connections[surface]),
        )

    def disconnect(self, websocket: WebSocket, surface: str):
        if surface in self.active_connections:
            self.active_connections[surface].discard(websocket)
            logger.info("websocket_client_disconnected", surface=surface)

    async def broadcast(self, message: dict):
        payload = json.dumps(message)
        for surface_clients in self.active_connections.values():
            for connection in list(surface_clients):
                try:
                    await connection.send_text(payload)
                except Exception as e:  # noqa: BLE001
                    logger.debug("websocket_send_failed", error=str(e))


manager = ConnectionManager()


async def broadcast_event(event_type: str, session_id: str, payload: dict) -> None:
    """Helper to broadcast structured server events to all connected clients."""
    message = {
        "event_type": event_type,
        "session_id": session_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "payload": payload,
    }
    await manager.broadcast(message)


@ws_router.websocket("/ws/nexus")
async def nexus_websocket(
    websocket: WebSocket,
    client_surface: str = Query(default="dashboard"),
    session_id: str = Query(default="default"),
):
    await manager.connect(websocket, client_surface)
    # Send connection welcome event
    welcome_event = {
        "event_type": "dag.updated",
        "session_id": session_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "payload": {
            "status": "connected",
            "message": f"Connected to NEXUS Core Event Bus as [{client_surface}]",
        },
    }
    await websocket.send_text(json.dumps(welcome_event))

    try:
        while True:
            raw_data = await websocket.receive_text()
            try:
                data = json.loads(raw_data)
                event_type = data.get("event_type", "unknown")
                # Echo receipt acknowledgement
                ack = {
                    "event_type": "audit.recorded",
                    "session_id": session_id,
                    "timestamp": datetime.now(UTC).isoformat(),
                    "payload": {
                        "received_event": event_type,
                        "status": "acknowledged",
                    },
                }
                await websocket.send_text(json.dumps(ack))
            except json.JSONDecodeError:
                await websocket.send_text(
                    json.dumps(
                        {
                            "event_type": "error",
                            "session_id": session_id,
                            "timestamp": datetime.now(UTC).isoformat(),
                            "payload": {"error": "Invalid JSON format"},
                        }
                    )
                )
    except WebSocketDisconnect:
        pass
    except Exception as e:  # noqa: BLE001
        logger.warning("websocket_exception_encountered", error=str(e), surface=client_surface)
    finally:
        manager.disconnect(websocket, client_surface)
