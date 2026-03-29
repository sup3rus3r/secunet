"""
Commander write pipeline — single entry point for all context writes.
Called by: comm hub (messages), execution API (commands),
           agents (findings via /commander/write), summariser (summaries).

Commander is the SOLE writer to the vector store.
Every write also goes to cold storage (immutable audit log).
"""
import uuid
import json
import logging
from datetime import datetime, timezone

from commander import rolling_window, vector_store, cold_storage, summariser
from commander.mission_state import get_state
from comm_hub import broadcaster
from shared.event_types import EVT_SUMMARY

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _event_to_text(event: dict) -> str:
    """Convert an event dict to a natural-language string for embedding."""
    etype   = event.get("event_type", "event")
    agent   = event.get("agent_id", "system")
    ts      = event.get("timestamp", "")[:19]

    # Build a readable representation
    parts = [f"{etype} from {agent} at {ts}"]
    for key, val in event.items():
        if key in ("event_type", "agent_id", "timestamp", "mission_id", "event_id"):
            continue
        if isinstance(val, (str, int, float, bool)):
            parts.append(f"{key}={val}")
        elif isinstance(val, (list, dict)):
            parts.append(f"{key}={json.dumps(val)[:100]}")
    return ". ".join(parts)


async def write_event(event_type: str, payload: dict) -> None:
    """
    Single entry point for all context writes.

    1. Enrich with standard metadata
    2. Push to rolling window (Layer 1)
    3. Embed + store in vector store (Layer 2)
    4. Check if rolling window needs compression
    5. Write to cold storage (always, no exceptions)
    6. Broadcast to dashboard
    """
    mission = get_state()

    enriched = {
        **payload,
        "event_id":   payload.get("event_id", str(uuid.uuid4())),
        "event_type": event_type,
        "timestamp":  payload.get("timestamp", _now()),
        "mission_id": mission.get("mission_id", ""),
    }

    agent_id = enriched.get("agent_id", "system")

    # 1. Layer 1 — rolling window
    try:
        await rolling_window.push(agent_id, enriched)
    except Exception as exc:
        logger.warning("Rolling window write failed: %s", exc)

    # 2. Layer 2 — vector store (skip summary type to avoid re-embedding summaries twice)
    if event_type != EVT_SUMMARY:
        try:
            text_repr = _event_to_text(enriched)
            # Build safe metadata (ChromaDB only accepts str/int/float/bool)
            metadata = {
                "event_type": enriched.get("event_type", ""),
                "agent_id":   agent_id,
                "mission_id": enriched.get("mission_id", ""),
                "timestamp":  enriched.get("timestamp", ""),
                "host":       str(enriched.get("host", "")),
            }
            vector_store.add(
                documents=[text_repr],
                metadatas=[metadata],
                ids=[enriched["event_id"]],
            )
        except Exception as exc:
            logger.warning("Vector store write failed: %s", exc)
    else:
        # Summaries get embedded with their content directly
        try:
            content = enriched.get("content", _event_to_text(enriched))
            vector_store.add(
                documents=[content],
                metadatas=[{
                    "event_type": EVT_SUMMARY,
                    "agent_id":   agent_id,
                    "mission_id": enriched.get("mission_id", ""),
                    "timestamp":  enriched.get("timestamp", ""),
                    "host":       "",
                }],
                ids=[enriched["event_id"]],
            )
        except Exception as exc:
            logger.warning("Vector store summary write failed: %s", exc)

    # 3. Check if rolling window needs compression
    try:
        if await rolling_window.needs_compression(agent_id):
            import asyncio
            asyncio.create_task(summariser.compress(agent_id))
    except Exception as exc:
        logger.warning("Compression check failed: %s", exc)

    # 4. Cold storage — always, no exceptions skipped silently
    await cold_storage.insert("events", enriched)

    # 5. Broadcast to dashboard (event type already set in enriched)
    try:
        await broadcaster.manager.send(enriched)
    except Exception as exc:
        logger.warning("Broadcast failed: %s", exc)
