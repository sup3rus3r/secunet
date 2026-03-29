"""
Message router.
All messages flow to Commander. Commander is the sole entity that tasks agents.
Agents never receive messages from anyone other than Commander.

Routing rules:
  - Engineer message          → Commander inbox + dashboard broadcast
  - Agent result/status       → Commander inbox only (no dashboard — Commander decides what to surface)
  - Agent chat (to engineer)  → Commander inbox + dashboard broadcast
  - @engineer in any message  → HITL queue
  - Always write to Commander context store
"""
import uuid
import logging
from datetime import datetime, timezone

from comm_hub import broadcaster, redis_bus
from shared.event_types import AGENT_MESSAGE, HUMAN_MESSAGE, EVT_MESSAGE

logger = logging.getLogger(__name__)

COMMANDER_INBOX = "agent.commander.inbox"


async def route_message(message: dict) -> None:
    sender   = message.get("from_id", "unknown")
    content  = message.get("content", "")
    msg_type = message.get("type", "chat")

    # Everything goes to Commander — Commander decides what happens next
    await redis_bus.publish(COMMANDER_INBOX, message)

    # HITL requests always go to the HITL queue
    if msg_type == "hitl" or "@engineer" in content:
        await redis_bus.publish("hitl.inbox", message)

    # Dashboard broadcast rules:
    # - Engineer messages → always show (it's their own message)
    # - Agent chat directed at engineer → show (Commander chose to surface it)
    # - Agent results/status → don't show (raw agent output, Commander summarises)
    should_broadcast = (
        sender == "engineer"
        or (sender not in ("engineer",) and msg_type == "chat")
    )

    if should_broadcast:
        event_type = HUMAN_MESSAGE if sender == "engineer" else AGENT_MESSAGE
        await broadcaster.manager.send({
            "type":       event_type,
            "message_id": message.get("message_id", _uuid()),
            "from_id":    sender,
            "to":         message.get("to", "commander"),
            "content":    content,
            "timestamp":  message.get("timestamp", _now()),
            "metadata":   message.get("metadata", {}),
        })

    # Write to Commander context store
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
