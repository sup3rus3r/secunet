"""
Rolling window compressor.
When an agent thread exceeds COMPRESSION_THRESHOLD, the oldest half
is compressed into a summary paragraph via LLM call.
The summary is written back through the write_pipeline so it lands
in both the vector store and cold storage.
Nothing is lost — events become semantically retrievable summaries.
"""
import os
import json
import logging
from datetime import datetime, timezone

from commander import rolling_window, summary_cache
from shared.event_types import EVT_SUMMARY
from llm_client import complete as llm_complete

logger = logging.getLogger(__name__)

# Compression uses the cheapest available model per provider
_COMPRESSION_MODELS = {
    "anthropic": "claude-haiku-4-5-20251001",
    "openai":    "gpt-4o-mini",
    "lmstudio":  os.getenv("LLM_MODEL", "local-model"),
}
_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic").lower()
MODEL = os.getenv("LLM_COMPRESSION_MODEL", _COMPRESSION_MODELS.get(_PROVIDER, "claude-haiku-4-5-20251001"))


SYSTEM_PROMPT = """You are the intelligence compression system for a purple team security platform.
Compress the provided security operation events into a concise intelligence summary.
Preserve ALL technical details: IPs, ports, CVEs, MITRE ATT&CK technique IDs, credentials found,
services identified, exploit outcomes, detection scores, patches deployed.
Write in plain text. Be precise and technical. Under 250 words."""


def _format_events(events: list[dict]) -> str:
    lines = []
    for e in events:
        ts        = e.get("timestamp", "")[:19]
        agent     = e.get("agent_id", "unknown")
        etype     = e.get("event_type", "event")
        # Remove large fields before formatting
        display   = {k: v for k, v in e.items()
                     if k not in ("timestamp", "agent_id", "event_type", "mission_id", "event_id")}
        lines.append(f"[{ts}] {agent} / {etype}: {json.dumps(display)[:300]}")
    return "\n".join(lines)


async def compress(agent_id: str) -> None:
    """
    Compress oldest half of agent's rolling window into a summary.
    Called by write_pipeline when threshold is reached.
    """
    events = await rolling_window.get_oldest_half(agent_id)
    if not events:
        return

    logger.info("Compressing %d events for %s", len(events), agent_id)

    try:
        summary_text = await llm_complete(
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _format_events(events)}],
            max_tokens=4096,
            model=MODEL,
        )
    except Exception as exc:
        logger.error("Summariser LLM call failed: %s", exc)
        # Fallback: concatenate key fields
        summary_text = f"[Compression failed] {len(events)} events from {agent_id}. " \
                       f"First: {events[0].get('event_type')} Last: {events[-1].get('event_type')}"

    now = datetime.now(timezone.utc).isoformat()
    summary = {
        "agent_id":    agent_id,
        "event_type":  EVT_SUMMARY,
        "content":     summary_text,
        "covers_from": events[0].get("timestamp", now),
        "covers_to":   events[-1].get("timestamp", now),
        "event_count": len(events),
        "timestamp":   now,
    }

    # Write back through the pipeline (embeds into vector store + cold log)
    from commander.write_pipeline import write_event
    await write_event(EVT_SUMMARY, summary)

    # Store in summary cache
    await summary_cache.store(summary)

    # Remove the compressed events from the rolling window
    await rolling_window.remove_oldest_half(agent_id)

    logger.info("Compression complete for %s — summary stored", agent_id)
