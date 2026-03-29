"""
HITL (Human-in-the-Loop) queue.
Agents push approval requests here. The dashboard reads and resolves them.
Phase 1: in-memory store. Phase 2: moves to Redis.
"""
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status

from comm_hub import broadcaster, redis_bus
from shared.message_schema import HitlRequest, HitlDecision
from shared.event_types import HITL_REQUEST, HITL_RESOLVED

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/hitl", tags=["hitl"])

# In-memory store for Phase 1 — keyed by hitl_id
_queue: dict[str, dict] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_hitl_request(req: HitlRequest) -> dict:
    """
    Called by an agent when a high-risk action requires engineer approval.
    Stores the request and broadcasts it to the dashboard.
    """
    entry = req.model_dump()
    _queue[req.hitl_id] = entry

    logger.warning(
        "HITL request from %s: %s [%s]",
        req.requesting_agent, req.action, req.risk_level
    )

    # Broadcast to dashboard — triggers the HITL approval panel
    await broadcaster.manager.send({
        "type":             HITL_REQUEST,
        "hitl_id":         req.hitl_id,
        "requesting_agent": req.requesting_agent,
        "action":          req.action,
        "risk_level":      req.risk_level,
        "context":         req.context,
        "proposed_command": req.proposed_command,
        "target":          req.target,
        "created_at":      req.created_at,
        "status":          "pending",
    })

    # Also publish to agent's inbox so it can poll/wait
    await redis_bus.publish(
        f"hitl.{req.hitl_id}.result",
        {"hitl_id": req.hitl_id, "status": "pending"}
    )

    return {"hitl_id": req.hitl_id, "status": "pending"}


@router.get("")
async def list_pending() -> dict:
    """Return all pending HITL requests."""
    pending = [v for v in _queue.values() if v["status"] == "pending"]
    return {"requests": pending, "count": len(pending)}


@router.get("/{hitl_id}")
async def get_hitl(hitl_id: str) -> dict:
    entry = _queue.get(hitl_id)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return entry


@router.post("/{hitl_id}/resolve")
async def resolve_hitl(hitl_id: str, decision: HitlDecision) -> dict:
    """
    Called when engineer approves or rejects a HITL request.
    Can be triggered from dashboard UI or via @agent chat reply (Phase 2).
    """
    entry = _queue.get(hitl_id)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if entry["status"] != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Request already resolved: {entry['status']}",
        )

    entry["status"]         = "approved" if decision.approved else "rejected"
    entry["resolved_by"]    = "engineer"
    entry["resolved_at"]    = _now()
    entry["resolution_note"] = decision.note or ""

    verdict = "approved" if decision.approved else "rejected"
    logger.info("HITL %s %s by engineer", hitl_id, verdict)

    # Broadcast resolution to dashboard
    await broadcaster.manager.send({
        "type":          HITL_RESOLVED,
        "hitl_id":      hitl_id,
        "approved":     decision.approved,
        "resolved_by":  "engineer",
        "resolved_at":  entry["resolved_at"],
        "note":         entry["resolution_note"],
    })

    # Publish resolution so waiting agent can unblock
    await redis_bus.publish(
        f"hitl.{hitl_id}.result",
        {
            "hitl_id":  hitl_id,
            "approved": decision.approved,
            "status":   verdict,
            "note":     entry["resolution_note"],
        }
    )

    return {"hitl_id": hitl_id, "status": verdict}
