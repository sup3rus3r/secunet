"""
Message router.
Parses @mentions, dispatches to agent Redis inboxes,
always broadcasts to the dashboard WebSocket, always writes
to the Commander context store.
"""
import re
import uuid
import logging
from datetime import datetime, timezone

from comm_hub import broadcaster, redis_bus
from shared.event_types import AGENT_MESSAGE, HUMAN_MESSAGE, EVT_MESSAGE

logger = logging.getLogger(__name__)

AGENT_IDS = ["recon", "exploit", "detect", "remediate", "monitor", "commander"]
MENTION_PATTERN = re.compile(
    r"@(recon|exploit|detect|remediate|monitor|commander|engineer|all)",
    re.IGNORECASE,
)


def extract_mentions(content: str) -> list[str]:
    return [m.lower() for m in MENTION_PATTERN.findall(content)]


async def route_message(message: dict) -> None:
    """
    Entry point for all messages — from engineer (via WS) or agents (via HTTP).

    Routing rules:
      - Engineer, no @mention     → commander only (commander coordinates agents)
      - Engineer, @all            → all agent inboxes
      - Engineer, @specific       → that agent's inbox only
      - Agent, @specific/@all     → mentioned agents' inboxes
      - Agent, no @mention        → dashboard only (no agent inboxes)
      - @engineer in any message  → HITL queue
      - Always broadcast to dashboard WebSocket
      - Always write to Commander context store
    """
    sender   = message.get("from_id", "unknown")
    content  = message.get("content", "")
    mentions = extract_mentions(content)

    # Determine recipients
    if "all" in mentions:
        recipients = AGENT_IDS
    elif mentions:
        recipients = [m for m in mentions if m != "engineer"]
    elif sender == "engineer":
        recipients = ["commander"]   # engineer → commander only; commander routes further
    else:
        recipients = []              # agent with no @mention → dashboard only

    # Dispatch to agent inboxes via Redis pub/sub
    for agent_name in recipients:
        channel = f"agent.{agent_name}.inbox"
        await redis_bus.publish(channel, message)

    # If @engineer mentioned: push to HITL queue channel
    if "engineer" in mentions:
        await redis_bus.publish("hitl.inbox", message)

    # Always broadcast to all dashboard WebSocket connections
    event_type = HUMAN_MESSAGE if sender == "engineer" else AGENT_MESSAGE
    await broadcaster.manager.send({
        "type":       event_type,
        "message_id": message.get("message_id", _uuid()),
        "from_id":    sender,
        "to":         mentions or ["all"],
        "content":    content,
        "timestamp":  message.get("timestamp", _now()),
        "metadata":   message.get("metadata", {}),
    })

    # Always write to Commander context store (Phase 2 wires this fully)
    await _write_to_commander(message)


async def _write_to_commander(message: dict) -> None:
    """Stub — wired fully in Phase 2 when write_pipeline is built."""
    try:
        from commander.write_pipeline import write_event
        await write_event(EVT_MESSAGE, message)
    except ImportError:
        pass  # Phase 2 not built yet


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _uuid() -> str:
    return str(uuid.uuid4())
