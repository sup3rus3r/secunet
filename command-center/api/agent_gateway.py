"""
Agent registration and health API.
Agents POST here on boot and send periodic heartbeats.
The registry is stored in Redis so it survives CC restarts.
"""
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status

from comm_hub import redis_bus, broadcaster
from shared.message_schema import AgentRegistration
from shared.event_types import AGENT_STATUS, AGENT_HEALTH

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agents", tags=["agents"])

REGISTRY_KEY = "secunet:agent_registry"
HEARTBEAT_TTL = 60  # seconds — agent considered offline if no heartbeat


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_agent(reg: AgentRegistration) -> dict:
    """
    Called by each agent container on boot.
    Stores registration in Redis and broadcasts status to dashboard.
    """
    entry = reg.model_dump()
    entry["registered_at"] = _now()
    entry["last_heartbeat"] = _now()
    entry["online"] = True

    # Store in Redis hash: field = agent_id, value = JSON
    await redis_bus.set_key(f"secunet:agent:{reg.id}", entry)

    logger.info("Agent registered: %s (%s)", reg.id, reg.display_name)

    await broadcaster.manager.send({
        "type":         AGENT_STATUS,
        "agent_id":     reg.id,
        "display_name": reg.display_name,
        "status":       reg.status,
        "online":       True,
        "timestamp":    _now(),
    })

    return {"registered": True, "agent_id": reg.id}


@router.post("/{agent_id}/heartbeat")
async def heartbeat(agent_id: str, payload: dict = {}) -> dict:
    """
    Called by agents on a regular interval (every ~15s).
    Updates last_heartbeat and current_task in registry.
    Broadcasts health update to dashboard.
    """
    entry = await redis_bus.get_key(f"secunet:agent:{agent_id}")
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agent_id!r} not registered",
        )

    entry["last_heartbeat"] = _now()
    entry["online"] = True
    if "current_task" in payload:
        entry["current_task"] = payload["current_task"]
    if "status" in payload:
        entry["status"] = payload["status"]

    await redis_bus.set_key(f"secunet:agent:{agent_id}", entry)

    await broadcaster.manager.send({
        "type":         AGENT_HEALTH,
        "agent_id":     agent_id,
        "online":       True,
        "status":       entry.get("status", "active"),
        "current_task": entry.get("current_task", ""),
        "timestamp":    _now(),
    })

    return {"ok": True}


@router.get("")
async def list_agents() -> dict:
    """Return all registered agents and their current status."""
    client = redis_bus.get_client()
    keys = await client.keys("secunet:agent:*")
    agents = []
    for key in keys:
        entry = await redis_bus.get_key(key)
        if entry:
            agents.append(entry)
    return {"agents": agents, "count": len(agents)}


@router.get("/{agent_id}")
async def get_agent(agent_id: str) -> dict:
    entry = await redis_bus.get_key(f"secunet:agent:{agent_id}")
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agent_id!r} not found",
        )
    return entry
