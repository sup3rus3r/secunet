"""
Layer 3 — Summary Cache.
LLM-compressed history paragraphs generated when rolling window overflows.
Summaries are also embedded into the vector store for semantic retrieval.
In-memory for fast access; also persisted to Redis.
"""
import json
import logging
from datetime import datetime, timezone
from comm_hub import redis_bus

logger = logging.getLogger(__name__)

_cache: list[dict] = []   # in-memory mirror for fast access
CACHE_KEY = "secunet:summaries"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def store(summary: dict) -> None:
    """Persist a new summary (called by summariser after compression)."""
    _cache.append(summary)
    await redis_bus.rpush(CACHE_KEY, summary)
    logger.debug("Summary stored for agent %s", summary.get("agent_id"))


async def load_all() -> None:
    """Reload cache from Redis on startup."""
    global _cache
    _cache = await redis_bus.lrange(CACHE_KEY, 0, -1)
    logger.info("Summary cache loaded: %d summaries", len(_cache))


def get_all() -> list[dict]:
    return list(_cache)


def get_relevant(query: str, limit: int = 3) -> list[dict]:
    """
    Return the most relevant summaries for a query.
    Simple implementation: return the most recent `limit` summaries.
    The vector store provides semantic retrieval — summaries are embedded there too.
    """
    return _cache[-limit:] if _cache else []


def get_by_agent(agent_id: str, limit: int = 5) -> list[dict]:
    return [s for s in _cache if s.get("agent_id") == agent_id][-limit:]
