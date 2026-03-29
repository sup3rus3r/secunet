"""
Cold Storage — PostgreSQL immutable audit log.
Write-only from the context pipeline. Never queried for active context.
Used for compliance, reports, and full mission replay.

Gracefully disabled if POSTGRES_URL is not set.
"""
import os
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_pool = None
POSTGRES_URL = os.getenv("POSTGRES_URL", "")

CREATE_EVENTS_TABLE = """
CREATE TABLE IF NOT EXISTS events (
    id          BIGSERIAL PRIMARY KEY,
    event_id    TEXT        NOT NULL,
    event_type  TEXT        NOT NULL,
    agent_id    TEXT        NOT NULL DEFAULT 'system',
    mission_id  TEXT        NOT NULL DEFAULT '',
    timestamp   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    payload     JSONB       NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_events_agent    ON events(agent_id);
CREATE INDEX IF NOT EXISTS idx_events_type     ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_mission  ON events(mission_id);
"""

CREATE_EGRESS_TABLE = """
CREATE TABLE IF NOT EXISTS egress_log (
    id         BIGSERIAL PRIMARY KEY,
    agent_id   TEXT        NOT NULL,
    url        TEXT        NOT NULL,
    method     TEXT        NOT NULL DEFAULT 'GET',
    timestamp  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


async def init() -> None:
    global _pool
    if not POSTGRES_URL:
        logger.warning("POSTGRES_URL not set — cold storage disabled")
        return
    try:
        import asyncpg
        _pool = await asyncpg.create_pool(POSTGRES_URL, min_size=1, max_size=5)
        async with _pool.acquire() as conn:
            await conn.execute(CREATE_EVENTS_TABLE)
            await conn.execute(CREATE_EGRESS_TABLE)
        logger.info("Cold storage (PostgreSQL) ready")
    except Exception as exc:
        logger.warning("Cold storage unavailable: %s", exc)
        _pool = None


async def insert(table: str, record: dict) -> None:
    """
    Insert a record into the audit log.
    Silently drops if Postgres is unavailable — mission continues.
    """
    if _pool is None:
        return
    try:
        if table == "events":
            async with _pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO events
                        (event_id, event_type, agent_id, mission_id, timestamp, payload)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    record.get("event_id", ""),
                    record.get("event_type", "generic"),
                    record.get("agent_id", "system"),
                    record.get("mission_id", ""),
                    datetime.now(timezone.utc),
                    json.dumps(record),
                )
        elif table == "egress_log":
            async with _pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO egress_log (agent_id, url, method)
                    VALUES ($1, $2, $3)
                    """,
                    record.get("agent_id", "system"),
                    record.get("url", ""),
                    record.get("method", "GET"),
                )
    except Exception as exc:
        logger.warning("Cold storage insert failed (table=%s): %s", table, exc)


async def query_events(event_type: str, limit: int = 200) -> list[dict]:
    """
    Fetch events by type from cold storage for report generation.
    Returns empty list if Postgres unavailable.
    """
    if _pool is None:
        return []
    try:
        async with _pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT payload FROM events
                WHERE event_type = $1
                ORDER BY timestamp DESC
                LIMIT $2
                """,
                event_type,
                limit,
            )
            return [json.loads(row["payload"]) for row in rows]
    except Exception as exc:
        logger.warning("Cold storage query failed: %s", exc)
        return []


async def truncate_events() -> None:
    """Delete all events from cold storage (session reset)."""
    if not _pool:
        return
    async with _pool.acquire() as conn:
        await conn.execute("DELETE FROM events")

async def close() -> None:
    if _pool:
        await _pool.close()
