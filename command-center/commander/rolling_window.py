"""
Layer 1 — Rolling Window (Redis).
Per-agent list of raw recent events.
Provides immediate recency context for LLM calls.
"""
import os
import logging
from comm_hub import redis_bus

logger = logging.getLogger(__name__)

WINDOW_SIZE      = int(os.getenv("ROLLING_WINDOW_SIZE", "15"))
COMPRESSION_THRESHOLD = int(os.getenv("COMPRESSION_THRESHOLD", "20"))


def _key(agent_id: str) -> str:
    return f"secunet:window:{agent_id}"


async def push(agent_id: str, event: dict) -> None:
    """Append event to agent's rolling window. Trims to WINDOW_SIZE."""
    key = _key(agent_id)
    await redis_bus.rpush(key, event)
    # Keep only the most recent WINDOW_SIZE * 2 to avoid unbounded growth
    # (compression keeps real size at WINDOW_SIZE)
    length = await redis_bus.llen(key)
    if length > WINDOW_SIZE * 2:
        await redis_bus.ltrim(key, -WINDOW_SIZE * 2, -1)


async def get(agent_id: str, limit: int = 10) -> list[dict]:
    """Return the most recent `limit` events for an agent."""
    key = _key(agent_id)
    total = await redis_bus.llen(key)
    start = max(0, total - limit)
    return await redis_bus.lrange(key, start, -1)


async def get_oldest_half(agent_id: str) -> list[dict]:
    """Return the oldest half of the window (for compression)."""
    key = _key(agent_id)
    total = await redis_bus.llen(key)
    half = total // 2
    if half == 0:
        return []
    return await redis_bus.lrange(key, 0, half - 1)


async def remove_oldest_half(agent_id: str) -> None:
    """Remove the oldest half after compression."""
    key = _key(agent_id)
    total = await redis_bus.llen(key)
    half = total // 2
    if half > 0:
        await redis_bus.ltrim(key, half, -1)


async def size(agent_id: str) -> int:
    return await redis_bus.llen(_key(agent_id))


async def needs_compression(agent_id: str) -> bool:
    return await size(agent_id) >= COMPRESSION_THRESHOLD
