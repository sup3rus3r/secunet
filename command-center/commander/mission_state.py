"""
Live mission state object.
Phase 1: in-memory. Phase 2: Redis-backed with persistence.
"""
import os
import uuid
from datetime import datetime, timezone

_state: dict = {}


def _init() -> dict:
    return {
        "mission_id":            str(uuid.uuid4()),
        "mission_name":          os.getenv("MISSION_NAME", "SecuNet"),
        "target_scope":          os.getenv("TARGET_SCOPE", ""),
        "start_time":            datetime.now(timezone.utc).isoformat(),
        "current_phase":         "recon",
        "hosts_discovered":      0,
        "hosts_tested":          0,
        "open_findings":         0,
        "critical_findings":     0,
        "high_findings":         0,
        "patches_deployed":      0,
        "attack_coverage_pct":   0,
        "detection_score_pct":   0,
        "active_agents":         [],
        "paused_agents":         [],
        "pending_hitl_requests": 0,
        "last_updated":          datetime.now(timezone.utc).isoformat(),
    }


def get_state() -> dict:
    global _state
    if not _state:
        _state = _init()
    return _state


def set_mission_control(command: str) -> None:
    """
    command: 'pause' | 'resume' | 'kill' | 'force-hitl'
    Agents poll /mission/control to check for directives.
    """
    update("mission_control", command)


def get_mission_control() -> str:
    """Returns current directive: 'run' | 'pause' | 'kill' | 'force-hitl'"""
    return get_state().get("mission_control", "run")


def update(field: str, value) -> None:
    global _state
    if not _state:
        _state = _init()
    _state[field] = value
    _state["last_updated"] = datetime.now(timezone.utc).isoformat()


def increment(field: str, amount: int = 1) -> None:
    global _state
    if not _state:
        _state = _init()
    _state[field] = _state.get(field, 0) + amount
    _state["last_updated"] = datetime.now(timezone.utc).isoformat()


def reset() -> None:
    """Reset mission state metrics to zero while preserving scope and mission name."""
    global _state
    current_scope = (_state or {}).get("target_scope", os.getenv("TARGET_SCOPE", ""))
    _state = _init()
    _state["target_scope"] = current_scope  # keep scope across session reset
