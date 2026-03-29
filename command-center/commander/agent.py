"""
Commander Agent — the intelligence captain.
Subscribes to its own inbox, responds to @commander queries,
maintains mission awareness, and keeps the context store current.
Runs as a background asyncio task inside the Command Center.
"""
import os
import uuid
import asyncio
import logging
from datetime import datetime, timezone

from commander.context_engine import query_context
from commander.write_pipeline import write_event
from commander.mission_state import get_state, update as update_state
from comm_hub import redis_bus, broadcaster
from shared.event_types import AGENT_MESSAGE, EVT_MESSAGE
from llm_client import complete as llm_complete

logger = logging.getLogger(__name__)

INBOX_CHANNEL = "agent.commander.inbox"

SYSTEM_PROMPT = """You are the Commander, the intelligence officer of SecuNet — an autonomous purple team platform.
Your role:
- Maintain the complete operational picture of the mission
- Answer context queries from operational agents with precision
- Brief agents with everything they need to act effectively
- Track mission state: discovered assets, findings, coverage, patch status
- Communicate clearly and technically

You have access to the full mission history via your memory layers.
When answering, always include specific technical details: IPs, CVEs, technique IDs, service versions.
Keep responses concise and actionable. You are always on."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _respond(message: dict) -> None:
    """Process an incoming message and generate a Commander response."""
    sender  = message.get("from_id", "unknown")
    content = message.get("content", "")

    # Build context for this query
    try:
        context = await query_context("commander", content)
    except Exception:
        context = "Context retrieval failed."

    mission = get_state()
    mission_summary = (
        f"Mission: {mission.get('mission_name')} | "
        f"Phase: {mission.get('current_phase')} | "
        f"Scope: {mission.get('target_scope')} | "
        f"Hosts: {mission.get('hosts_discovered')} | "
        f"Open findings: {mission.get('open_findings')} | "
        f"HITL pending: {mission.get('pending_hitl_requests')}"
    )

    user_msg = f"MESSAGE FROM {sender.upper()}: {content}\n\nMISSION STATE: {mission_summary}\n\nCONTEXT:\n{context}"

    try:
        reply_text = await llm_complete(
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
    except Exception as exc:
        logger.error("Commander LLM call failed: %s", exc)
        reply_text = f"Commander offline: {exc}"

    msg_id = str(uuid.uuid4())
    reply = {
        "message_id": msg_id,
        "from_id":    "commander",
        "to":         sender,
        "content":    reply_text,
        "type":       "chat",
        "timestamp":  _now(),
    }

    # Broadcast reply to dashboard
    await broadcaster.manager.send({
        "type":       AGENT_MESSAGE,
        "message_id": msg_id,
        "from_id":    "commander",
        "to":         [sender],
        "content":    reply_text,
        "timestamp":  _now(),
    })

    # Write reply to context store
    await write_event(EVT_MESSAGE, reply)

    # Publish reply back to the sender's inbox
    await redis_bus.publish(f"agent.{sender.replace('-agent','')}.inbox", reply)


async def run() -> None:
    """
    Subscribe to Commander inbox and process messages indefinitely.
    Launched as asyncio.create_task() from CC lifespan.
    """
    logger.info("Commander Agent listening on %s", INBOX_CHANNEL)

    async def handle(message: dict) -> None:
        try:
            await _respond(message)
        except Exception:
            logger.exception("Commander failed to process message")

    try:
        await redis_bus.subscribe(INBOX_CHANNEL, handle)
    except Exception as exc:
        logger.error("Commander Agent crashed: %s", exc)


async def update_mission_metric(field: str, value) -> None:
    """Called by other CC components to update mission state and broadcast."""
    update_state(field, value)
    mission = get_state()
    await broadcaster.manager.send({
        "type":      "mission.metric",
        "field":     field,
        "value":     value,
        "mission":   mission,
        "timestamp": _now(),
    })
