"""
Dashboard WebSocket endpoint.
Single persistent connection per dashboard client.
On connect: sends full mission state snapshot.
On message: routes through comm hub.
"""
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from comm_hub import broadcaster
from comm_hub.router import route_message
from shared.event_types import MISSION_STATE

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    await broadcaster.manager.connect(ws)
    try:
        # Send full mission state snapshot on connect
        await _send_initial_state(ws)

        # Listen for messages from the engineer
        while True:
            raw = await ws.receive_text()
            try:
                message = json.loads(raw)
                await route_message(message)
            except json.JSONDecodeError:
                logger.warning("Received non-JSON WebSocket message: %s", raw[:100])
            except Exception:
                logger.exception("Error routing WebSocket message")

    except WebSocketDisconnect:
        broadcaster.manager.disconnect(ws)


async def _send_initial_state(ws: WebSocket) -> None:
    """
    Send the full current mission state to a newly connected dashboard.
    This hydrates all panels on first load.
    """
    try:
        from commander.mission_state import get_state
        state = get_state()
    except ImportError:
        state = _default_state()

    await ws.send_text(json.dumps({
        "type": MISSION_STATE,
        "data": state,
    }))

    # Always send commander as online — it runs inside CC
    await ws.send_text(json.dumps({
        "type":     "agent.registered",
        "agent_id": "commander",
        "status":   "online",
    }))

    # Re-send status for all currently registered agents
    try:
        import redis.asyncio as aioredis
        import os, json as _json
        r = aioredis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"), decode_responses=True)
        keys = await r.keys("secunet:agent:*")
        for key in keys:
            data = await r.hgetall(key)
            if data.get("agent_id"):
                await ws.send_text(_json.dumps({
                    "type":     "agent.registered",
                    "agent_id": data["agent_id"],
                    "status":   data.get("status", "online"),
                }))
        await r.aclose()
    except Exception:
        pass


def _default_state() -> dict:
    """Minimal mission state for Phase 1 before Commander is wired."""
    return {
        "mission_id":            "",
        "mission_name":          "SecuNet",
        "target_scope":          "",
        "current_phase":         "idle",
        "hosts_discovered":      0,
        "hosts_tested":          0,
        "open_findings":         0,
        "critical_findings":     0,
        "high_findings":         0,
        "patches_deployed":      0,
        "attack_coverage_pct":   0,
        "detection_score_pct":   0,
        "active_agents":         [],
        "paused_agents":         [],
        "pending_hitl_requests": 0,
    }
