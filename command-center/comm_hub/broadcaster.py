"""
WebSocket broadcast manager.
Maintains the set of connected dashboard clients and
sends typed event payloads to all of them.
"""
import json
import logging
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.add(ws)
        logger.info("Dashboard connected. Total connections: %d", len(self._connections))

    def disconnect(self, ws: WebSocket) -> None:
        self._connections.discard(ws)
        logger.info("Dashboard disconnected. Total connections: %d", len(self._connections))

    async def send(self, payload: dict) -> None:
        """Broadcast a typed event payload to all connected dashboards."""
        if not self._connections:
            return
        message = json.dumps(payload)
        dead: set[WebSocket] = set()
        for ws in self._connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self.disconnect(ws)

    @property
    def connection_count(self) -> int:
        return len(self._connections)


# Module-level singleton — imported everywhere that needs to broadcast
manager = ConnectionManager()
