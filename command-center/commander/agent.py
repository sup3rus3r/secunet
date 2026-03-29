"""
Commander Agent — the intelligence captain.

Subscribes to its own inbox, evaluates every incoming event, decides who
acts next, routes work in parallel, and maintains the full operational
picture.

Decision model — LLM returns JSON:
  reply    — text to surface to engineer in Comms feed (null = stay silent)
  tasks    — list of {agent, task} dispatched in parallel
  reasoning — brief decision trail written to context, never shown
"""
import re
import json
import uuid
import asyncio
import logging
from datetime import datetime, timezone

from commander.context_engine import query_context
from commander.write_pipeline import write_event
from commander.mission_state import get_state, update as update_state
from comm_hub import redis_bus, broadcaster
from shared.event_types import AGENT_MESSAGE, ACTIVITY_EVENT, EVT_MESSAGE
from llm_client import complete as llm_complete

logger = logging.getLogger(__name__)

INBOX_CHANNEL = "agent.commander.inbox"

# Agent roster: id → Redis inbox channel
AGENT_ROSTER = {
    "recon-agent":     "agent.recon.inbox",
    "exploit-agent":   "agent.exploit.inbox",
    "detect-agent":    "agent.detect.inbox",
    "remediate-agent": "agent.remediate.inbox",
    "monitor-agent":   "agent.monitor.inbox",
}

SYSTEM_PROMPT = """You are Commander, the intelligence officer of SecuNet — an autonomous purple team platform.

You receive messages from:
  - engineer       — the operator directing the engagement
  - recon-agent    — network discovery and service fingerprinting
  - exploit-agent  — vulnerability exploitation and proof-of-concept
  - detect-agent   — detection engineering, sigma rules, alert validation
  - remediate-agent — fix advisory, Ansible playbooks, remediation packages
  - monitor-agent  — continuous monitoring, tripwires, anomaly detection

Your job: evaluate every incoming event and decide what happens next.

Respond with ONLY valid JSON — no markdown fences, no explanation outside the JSON:
{
  "reply": "<message to show engineer in Comms feed — null if no engineer update needed>",
  "tasks": [
    {"agent": "<agent-id>", "task": "<specific actionable instruction>"}
  ],
  "reasoning": "<brief decision trail, stored not shown>"
}

Rules:
- tasks run in parallel — include multiple tasks when work can happen simultaneously
- on agent result: evaluate quality, decide next step; reply=null unless noteworthy for engineer
- on engineer message: always reply; include tasks if the request warrants agent action
- on agent status (startup/heartbeat): tasks=[], reply=null unless something requires attention
- be precise in tasks: include IPs, CVEs, service versions, technique IDs from context
- do not re-task an agent already working on the same objective"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _emit_activity(direction: str, actor: str, summary: str) -> None:
    """Broadcast one entry to the dashboard Activity Feed."""
    await broadcaster.manager.send({
        "type":      ACTIVITY_EVENT,
        "id":        str(uuid.uuid4()),
        "direction": direction,   # "inbound" | "outbound"
        "actor":     actor,
        "summary":   summary[:200],
        "timestamp": _now(),
    })


def _extract_json(text: str) -> str:
    """Pull the first {...} block out of an LLM response, tolerating fences."""
    clean = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", clean, re.DOTALL)
    if fence:
        return fence.group(1)
    start = clean.find("{")
    end   = clean.rfind("}")
    if start != -1 and end != -1:
        return clean[start:end + 1]
    return clean


async def _parse_decision(text: str) -> dict:
    try:
        return json.loads(_extract_json(text))
    except Exception:
        logger.warning("Commander decision JSON parse failed: %s", text[:300])
        return {"reply": None, "tasks": [], "reasoning": "parse_error"}


async def _dispatch_task(task: dict) -> None:
    """Publish a task to a specific agent inbox and emit an outbound activity event."""
    agent_id  = task.get("agent", "")
    task_text = task.get("task", "")
    if not agent_id or not task_text:
        return

    inbox = AGENT_ROSTER.get(agent_id, f"agent.{agent_id.replace('-agent','')}.inbox")

    task_msg = {
        "message_id": str(uuid.uuid4()),
        "from_id":    "commander",
        "to":         agent_id,
        "content":    task_text,
        "type":       "task",
        "timestamp":  _now(),
    }
    try:
        await redis_bus.publish(inbox, task_msg)
        await _emit_activity("outbound", agent_id, task_text)
        logger.info("Commander → %s: %s", agent_id, task_text[:80])
    except Exception as exc:
        logger.error("Commander failed to task %s: %s", agent_id, exc)


async def _respond(message: dict) -> None:
    """Evaluate one incoming message and act on Commander's decision."""
    sender   = message.get("from_id", "unknown")
    content  = message.get("content", "")
    msg_type = message.get("type", "chat")

    if not content:
        return

    # ── 1. Log inbound activity ──────────────────────────────────────────
    await _emit_activity("inbound", sender, content[:150].replace("\n", " "))

    # ── 2. Fast-path: agent status pings need no LLM decision ────────────
    if sender != "engineer" and msg_type == "status":
        await write_event(EVT_MESSAGE, message)
        return

    # ── 3. Build prompt ──────────────────────────────────────────────────
    try:
        context = await query_context("commander", content)
    except Exception:
        context = "Context retrieval unavailable."

    mission = get_state()
    mission_summary = (
        f"Mission: {mission.get('mission_name')} | "
        f"Phase: {mission.get('current_phase')} | "
        f"Scope: {mission.get('target_scope')} | "
        f"Hosts: {mission.get('hosts_discovered')} | "
        f"Open findings: {mission.get('open_findings')} | "
        f"HITL pending: {mission.get('pending_hitl_requests')}"
    )

    source_label = "ENGINEER REQUEST" if sender == "engineer" else f"{sender.upper()} {msg_type.upper()}"
    user_prompt = (
        f"{source_label}: {content}\n\n"
        f"MISSION STATE: {mission_summary}\n\n"
        f"RELEVANT CONTEXT:\n{context}"
    )

    # ── 4. LLM decision ──────────────────────────────────────────────────
    try:
        raw = await llm_complete(
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
    except Exception as exc:
        logger.error("Commander LLM call failed: %s", exc)
        raw = '{"reply": "Commander LLM error — check logs.", "tasks": [], "reasoning": "llm_error"}'

    decision   = await _parse_decision(raw)
    reply_text = decision.get("reply") or None
    tasks      = [t for t in (decision.get("tasks") or []) if t.get("agent") and t.get("task")]

    logger.info(
        "Commander decision | reply=%s tasks=%d | %s",
        bool(reply_text), len(tasks), decision.get("reasoning", "")[:100],
    )

    # ── 5. Surface reply to engineer (Comms feed) ────────────────────────
    if reply_text:
        msg_id = str(uuid.uuid4())
        await broadcaster.manager.send({
            "type":       AGENT_MESSAGE,
            "message_id": msg_id,
            "from_id":    "commander",
            "to":         "engineer",
            "content":    reply_text,
            "timestamp":  _now(),
        })
        await write_event(EVT_MESSAGE, {
            "message_id": msg_id,
            "from_id":    "commander",
            "to":         "engineer",
            "content":    reply_text,
            "type":       "chat",
            "timestamp":  _now(),
        })

    # ── 6. Dispatch tasks in parallel ────────────────────────────────────
    if tasks:
        await asyncio.gather(*[_dispatch_task(t) for t in tasks])

    # ── 7. Write original message to Commander context ───────────────────
    await write_event(EVT_MESSAGE, message)


async def run() -> None:
    """
    Subscribe to Commander inbox and process messages indefinitely.
    Launched as asyncio.create_task() from CC lifespan.
    """
    logger.info("Commander listening on %s", INBOX_CHANNEL)

    async def handle(message: dict) -> None:
        try:
            await _respond(message)
        except Exception:
            logger.exception("Commander failed to process message")

    try:
        await redis_bus.subscribe(INBOX_CHANNEL, handle)
    except Exception as exc:
        logger.error("Commander crashed: %s", exc)


async def update_mission_metric(field: str, value) -> None:
    """Called by other CC components to update mission state and broadcast."""
    update_state(field, value)
    mission = get_state()
    await broadcaster.manager.send({
        "type":      "mission.metric",
        "field":     field,
        "value":     value,
        "mission":   mission,
        "timestamp": _now(),
    })
