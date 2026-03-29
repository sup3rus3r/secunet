"""
Context assembly engine.
Assembles context from all three memory layers for any agent query.
Returns a synthesised answer under 500 tokens.

Called by: agents via POST /commander/query
"""
import os
import json
import logging

from commander import rolling_window, vector_store, summary_cache
from llm_client import complete as llm_complete

logger = logging.getLogger(__name__)

_COMPRESSION_MODELS = {
    "anthropic": "claude-haiku-4-5-20251001",
    "openai":    "gpt-4o-mini",
    "lmstudio":  os.getenv("LLM_MODEL", "local-model"),
}
_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic").lower()
MODEL = os.getenv("LLM_COMPRESSION_MODEL", _COMPRESSION_MODELS.get(_PROVIDER, "claude-haiku-4-5-20251001"))

SEMANTIC_RESULTS = int(os.getenv("SEMANTIC_RESULTS", "5"))
SUMMARY_RESULTS  = int(os.getenv("SUMMARY_RESULTS", "3"))

SYSTEM_PROMPT = """You are the Commander, the intelligence officer of a purple team security platform.
Your job is to answer context queries from operational agents.
Answer using ONLY the provided context. Be precise and technical.
Include all relevant IPs, CVEs, technique IDs, credentials, services, and findings.
Stay under 500 tokens. If the context does not contain the answer, say so explicitly."""

# Per-agent retrieval profiles — shapes what the vector store returns
RETRIEVAL_PROFILES: dict[str, list[str] | None] = {
    "recon-agent":     ["scan_result", "asset_discovery", "service_fingerprint", "summary", "message"],
    "exploit-agent":   ["scan_result", "vulnerability_finding", "credential_found",
                        "exploit_attempt", "access_path", "summary", "message"],
    "detect-agent":    ["exploit_attempt", "command_execution", "detection_score",
                        "alert_result", "summary", "message"],
    "remediate-agent": ["vulnerability_finding", "detection_score", "patch_deployed",
                        "hitl_approval", "summary", "message"],
    "monitor-agent":   ["asset_discovery", "patch_deployed", "vulnerability_finding",
                        "anomaly_event", "tripwire_state", "summary"],
    "commander":       None,  # full corpus, no filter
}


def _format_events(events: list[dict]) -> str:
    if not events:
        return "(none)"
    lines = []
    for e in events:
        ts    = e.get("timestamp", "")[:19]
        etype = e.get("event_type", "event")
        body  = {k: v for k, v in e.items()
                 if k not in ("timestamp", "event_type", "mission_id", "event_id")}
        lines.append(f"[{ts}] {etype}: {json.dumps(body)[:400]}")
    return "\n".join(lines)


def _format_chunks(chunks: list[dict]) -> str:
    if not chunks:
        return "(none)"
    lines = []
    for c in chunks:
        score = round(1 - c.get("distance", 0), 3)
        lines.append(f"[relevance={score}] {c['document'][:400]}")
    return "\n".join(lines)


def _format_summaries(summaries: list[dict]) -> str:
    if not summaries:
        return "(none)"
    lines = []
    for s in summaries:
        agent   = s.get("agent_id", "?")
        covers  = f"{s.get('covers_from','')[:19]} → {s.get('covers_to','')[:19]}"
        lines.append(f"[{agent} | {covers}]\n{s.get('content','')}")
    return "\n\n".join(lines)


async def query_context(agent_id: str, query: str) -> str:
    """
    Assemble context from all three layers and synthesise via LLM.
    Returns answer under 500 tokens.
    """
    if not query.strip():
        return "No query provided."

    # Layer 1: Recent raw events for this agent
    recent_events = await rolling_window.get(agent_id, limit=10)

    # Layer 2: Semantic retrieval filtered by agent's profile
    profile = RETRIEVAL_PROFILES.get(agent_id)
    where_filter = {"event_type": {"$in": profile}} if profile else None
    semantic_chunks = vector_store.query(
        query_text=query,
        n_results=SEMANTIC_RESULTS,
        where=where_filter,
    )

    # Layer 3: Relevant summary chunks
    relevant_summaries = summary_cache.get_relevant(query, limit=SUMMARY_RESULTS)

    # No context available yet (early mission)
    if not recent_events and not semantic_chunks and not relevant_summaries:
        return (
            f"No context available yet for query: {query!r}. "
            "Mission may be in early stages."
        )

    user_prompt = f"""QUERY FROM {agent_id.upper()}: {query}

RECENT EVENTS (Layer 1 — rolling window):
{_format_events(recent_events)}

SEMANTIC CONTEXT (Layer 2 — vector store):
{_format_chunks(semantic_chunks)}

HISTORY SUMMARIES (Layer 3 — summary cache):
{_format_summaries(relevant_summaries)}"""

    try:
        return await llm_complete(
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=4096,
            model=MODEL,
        )
    except Exception as exc:
        logger.error("Context engine LLM call failed: %s", exc)
        # Fallback: return raw recent events
        return f"[LLM unavailable] Recent events:\n{_format_events(recent_events[:5])}"
