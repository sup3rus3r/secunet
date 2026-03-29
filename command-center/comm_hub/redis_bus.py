"""
Redis pub/sub bus.
All inter-agent and agent↔CC messaging flows through here.
Each agent has a dedicated inbox channel: agent.{id}.inbox
"""
import json
import asyncio
import logging
from typing import Callable, Awaitable
import redis.asyncio as redis

logger = logging.getLogger(__name__)

_client: redis.Redis | None = None


async def init(url: str) -> None:
    global _client
    _client = redis.from_url(url, decode_responses=True)
    await _client.ping()
    logger.info("Redis connected: %s", url)


async def close() -> None:
    if _client:
        await _client.aclose()


def get_client() -> redis.Redis:
    if _client is None:
        raise RuntimeError("Redis not initialised — call init() first")
    return _client


async def publish(channel: str, payload: dict) -> None:
    await get_client().publish(channel, json.dumps(payload))


async def subscribe(
    channel: str,
    callback: Callable[[dict], Awaitable[None]],
) -> None:
    """
    Subscribe to a Redis channel and fire callback for every message.
    Runs indefinitely — call as an asyncio.create_task.
    """
    async with get_client().pubsub() as pubsub:
        await pubsub.subscribe(channel)
        logger.info("Subscribed to Redis channel: %s", channel)
        async for raw in pubsub.listen():
            if raw["type"] != "message":
                continue
            try:
                data = json.loads(raw["data"])
                await callback(data)
            except Exception:
                logger.exception("Error processing message on %s", channel)


async def set_key(key: str, value: dict, ttl: int | None = None) -> None:
    encoded = json.dumps(value)
    if ttl:
        await get_client().setex(key, ttl, encoded)
    else:
        await get_client().set(key, encoded)


async def get_key(key: str) -> dict | None:
    raw = await get_client().get(key)
    return json.loads(raw) if raw else None


async def delete_key(key: str) -> None:
    await get_client().delete(key)


async def rpush(key: str, value: dict) -> None:
    await get_client().rpush(key, json.dumps(value))


async def lrange(key: str, start: int = 0, end: int = -1) -> list[dict]:
    items = await get_client().lrange(key, start, end)
    return [json.loads(i) for i in items]


async def llen(key: str) -> int:
    return await get_client().llen(key)


async def ltrim(key: str, start: int, end: int) -> None:
    await get_client().ltrim(key, start, end)
