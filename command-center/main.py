"""
SecuNet Command Center
FastAPI application entry point.

Port: 8001
Serves: WebSocket (/ws), agent APIs, execution API, HITL queue
"""
import sys
import os
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

# Add repo root to path so `shared` is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from comm_hub import redis_bus, broadcaster
from api.scope_enforcer import load_scope
from api import websocket, agent_gateway, execution, hitl

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")


async def _register_commander():
    """Broadcast commander as online so the dashboard fleet panel shows correct status."""
    import asyncio
    await asyncio.sleep(1)  # let WS connections settle
    await broadcaster.manager.send({
        "type":     "agent.registered",
        "agent_id": "commander",
        "status":   "online",
    })


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio
    # ── Startup ──────────────────────────────────────────────
    logger.info("SecuNet Command Center starting...")

    # Connect to Redis
    await redis_bus.init(REDIS_URL)
    logger.info("Redis ready")

    # Load target scope
    load_scope()
    logger.info("Scope enforcer ready")

    # Phase 2 — Commander memory layer
    from commander import vector_store, cold_storage, summary_cache
    from commander import agent as commander_agent

    vector_store.init()
    logger.info("Vector store (ChromaDB) ready — %d documents", vector_store.count())

    await cold_storage.init()
    await summary_cache.load_all()
    logger.info("Commander memory layers ready")

    # Start Commander Agent background loop
    asyncio.create_task(commander_agent.run())
    logger.info("Commander Agent started")

    # Register Commander as online in the dashboard fleet
    asyncio.create_task(_register_commander())

    logger.info("Command Center fully operational on port 8001")
    yield

    # ── Shutdown ─────────────────────────────────────────────
    await cold_storage.close()
    await redis_bus.close()
    logger.info("Command Center shut down")


app = FastAPI(
    title="SecuNet Command Center",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────
app.include_router(websocket.router)
app.include_router(agent_gateway.router)
app.include_router(execution.router)
app.include_router(hitl.router)


# ── Messages endpoint (agents send messages via HTTP) ─────────
from fastapi import APIRouter
from comm_hub.router import route_message
from shared.message_schema import Message

messages_router = APIRouter(prefix="/messages", tags=["messages"])

@messages_router.post("/send")
async def send_message(message: Message) -> dict:
    """
    Agents call this to send a message through the comm hub.
    Routes @mentions, broadcasts to dashboard, writes to Commander.
    """
    await route_message(message.model_dump())
    return {"sent": True, "message_id": message.message_id}

app.include_router(messages_router)


# ── Commander endpoints (Phase 2 wires full logic) ────────────
from fastapi import APIRouter as _APIRouter

commander_router = _APIRouter(prefix="/commander", tags=["commander"])

@commander_router.post("/write")
async def commander_write(payload: dict) -> dict:
    """Write an event to the Commander context store."""
    from commander.write_pipeline import write_event
    event_type = payload.pop("event_type", "generic")
    await write_event(event_type, payload)
    return {"written": True}

@commander_router.post("/query")
async def commander_query(payload: dict) -> dict:
    """Query Commander for context. Phase 2 returns synthesised context."""
    try:
        from commander.context_engine import query_context
        agent_id = payload.get("agent_id", "unknown")
        query    = payload.get("query", "")
        context  = await query_context(agent_id, query)
        return {"context": context}
    except ImportError:
        return {"context": "Commander context engine not yet initialised."}

app.include_router(commander_router)


# ── Mission control ───────────────────────────────────────────
from commander.mission_state import (
    get_state as _get_mission_state,
    set_mission_control as _set_mission_control,
    get_mission_control as _get_mission_control,
)

mission_router = _APIRouter(prefix="/mission", tags=["mission"])

@mission_router.get("/state")
async def mission_state() -> dict:
    return _get_mission_state()

@mission_router.post("/pause")
async def mission_pause() -> dict:
    _set_mission_control("pause")
    await broadcaster.manager.send({"type": "mission.metric", "field": "mission_control", "value": "pause"})
    return {"ok": True, "directive": "pause"}

@mission_router.post("/resume")
async def mission_resume() -> dict:
    _set_mission_control("resume")
    await broadcaster.manager.send({"type": "mission.metric", "field": "mission_control", "value": "run"})
    return {"ok": True, "directive": "resume"}

@mission_router.post("/kill")
async def mission_kill() -> dict:
    _set_mission_control("kill")
    await broadcaster.manager.send({"type": "mission.metric", "field": "mission_control", "value": "kill"})
    return {"ok": True, "directive": "kill"}

@mission_router.post("/force-hitl")
async def mission_force_hitl() -> dict:
    _set_mission_control("force-hitl")
    await broadcaster.manager.send({"type": "mission.metric", "field": "mission_control", "value": "force-hitl"})
    return {"ok": True, "directive": "force-hitl"}

@mission_router.get("/control")
async def mission_control_poll() -> dict:
    """Agents poll this to check for directives."""
    directive = _get_mission_control()
    # Reset one-shot directives after agents have read them
    if directive in ("kill", "force-hitl"):
        _set_mission_control("run")
    return {"directive": directive}

@mission_router.post("/scope")
async def set_target_scope(payload: dict) -> dict:
    """Update target scope at runtime. Reloads scope enforcer + broadcasts to dashboard."""
    scope = (payload.get("scope") or "").strip()
    if not scope:
        return {"ok": False, "error": "scope is required"}
    from api.scope_enforcer import set_scope as _set_scope
    from commander.mission_state import update as _update_state
    _update_state("target_scope", scope)
    _set_scope([s.strip() for s in scope.split(",")])
    await broadcaster.manager.send({"type": "mission.metric", "field": "target_scope", "value": scope})
    return {"ok": True, "scope": scope}

@mission_router.post("/reset")
async def mission_reset() -> dict:
    """
    Full session reset.
    Clears: Redis context windows + summaries, ChromaDB collection,
    PostgreSQL events, mission state metrics.
    Broadcasts a clean mission.state to all dashboard clients.
    """
    import os as _os

    # 1. Redis — wipe rolling windows and summaries
    try:
        import redis.asyncio as _aioredis
        _r = _aioredis.from_url(_os.getenv("REDIS_URL", "redis://localhost:6379"), decode_responses=True)
        keys = await _r.keys("secunet:window:*")
        keys += await _r.keys("secunet:summaries")
        if keys:
            await _r.delete(*keys)
        await _r.aclose()
    except Exception as exc:
        logger.warning("Redis reset partial: %s", exc)

    # 2. ChromaDB — delete and recreate the collection
    try:
        from commander import vector_store
        vector_store.reset()
    except Exception as exc:
        logger.warning("ChromaDB reset partial: %s", exc)

    # 3. PostgreSQL — truncate events table
    try:
        from commander.cold_storage import truncate_events
        await truncate_events()
    except Exception as exc:
        logger.warning("PostgreSQL reset partial: %s", exc)

    # 4. Mission state — reset metrics to zero
    from commander.mission_state import reset as _reset_state
    _reset_state()

    # 5. Broadcast clean state to all dashboard clients
    from commander.mission_state import get_state as _get_state
    from shared.event_types import MISSION_STATE
    await broadcaster.manager.send({"type": MISSION_STATE, "data": _get_state()})

    return {"ok": True}

app.include_router(mission_router)


# ── Network helpers ────────────────────────────────────────────
import socket as _socket
import ipaddress as _ipaddress

@app.get("/network/local", tags=["mission"])
async def local_network() -> dict:
    """Return the host's primary local network CIDR (e.g. 192.168.1.0/24)."""
    try:
        # Connect to an external address to discover the outbound interface IP.
        # No data is actually sent.
        s = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        network = _ipaddress.IPv4Network(f"{ip}/24", strict=False)
        return {"ip": ip, "cidr": str(network)}
    except Exception as e:
        return {"ip": None, "cidr": None, "error": str(e)}


# ── Report ─────────────────────────────────────────────────────
report_router = _APIRouter(tags=["report"])

@report_router.get("/report")
async def generate_report() -> dict:
    """Generate a mission summary report from Commander cold storage."""
    from commander.cold_storage import query_events
    from commander.mission_state import get_state

    state = get_state()

    findings  = await query_events("vulnerability_finding", limit=500)
    exploits  = await query_events("exploit_attempt",       limit=200)
    patches   = await query_events("patch_deployed",        limit=200)
    detects   = await query_events("detection_score",       limit=50)

    return {
        "mission_id":          state.get("mission_id"),
        "mission_name":        state.get("mission_name"),
        "target_scope":        state.get("target_scope"),
        "start_time":          state.get("start_time"),
        "generated_at":        datetime.now(timezone.utc).isoformat(),
        "summary": {
            "hosts_discovered":    state.get("hosts_discovered", 0),
            "hosts_tested":        state.get("hosts_tested", 0),
            "open_findings":       state.get("open_findings", 0),
            "critical_findings":   state.get("critical_findings", 0),
            "high_findings":       state.get("high_findings", 0),
            "patches_deployed":    state.get("patches_deployed", 0),
            "attack_coverage_pct": state.get("attack_coverage_pct", 0),
            "detection_score_pct": state.get("detection_score_pct", 0),
        },
        "findings":  findings,
        "exploits":  exploits,
        "patches":   patches,
        "detection": detects,
    }

@report_router.get("/report/pdf")
async def generate_report_pdf():
    """Render and stream the mission report as a downloadable PDF."""
    from fastapi.responses import Response
    from commander.cold_storage import query_events
    from commander.mission_state import get_state
    from commander.report_builder import build_pdf

    state    = get_state()
    findings = await query_events("vulnerability_finding", limit=500)
    exploits = await query_events("exploit_attempt",       limit=200)
    patches  = await query_events("patch_deployed",        limit=200)

    data = {
        "mission_id":   state.get("mission_id"),
        "mission_name": state.get("mission_name"),
        "target_scope": state.get("target_scope"),
        "start_time":   state.get("start_time"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "hosts_discovered":    state.get("hosts_discovered",    0),
            "hosts_tested":        state.get("hosts_tested",        0),
            "open_findings":       state.get("open_findings",       0),
            "critical_findings":   state.get("critical_findings",   0),
            "high_findings":       state.get("high_findings",       0),
            "patches_deployed":    state.get("patches_deployed",    0),
            "attack_coverage_pct": state.get("attack_coverage_pct", 0),
            "detection_score_pct": state.get("detection_score_pct", 0),
        },
        "findings": findings,
        "exploits": exploits,
        "patches":  patches,
    }

    pdf_bytes = build_pdf(data)
    mission_slug = (state.get("mission_name") or "secunet").lower().replace(" ", "-")
    filename = f"secunet-report-{mission_slug}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

app.include_router(report_router)


# ── Health check ──────────────────────────────────────────────
@app.get("/health")
async def health() -> dict:
    from comm_hub.redis_bus import get_client
    try:
        await get_client().ping()
        redis_ok = True
    except Exception:
        redis_ok = False

    from commander.mission_state import get_state
    return {
        "status":       "ok",
        "service":      "command-center",
        "redis":        "ok" if redis_ok else "error",
        "mission":      get_state().get("mission_name"),
        "target_scope": get_state().get("target_scope"),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
