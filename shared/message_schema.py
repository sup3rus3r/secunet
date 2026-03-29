from __future__ import annotations
from typing import Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone
import uuid


def _uuid() -> str:
    return str(uuid.uuid4())

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Core message ──────────────────────────────────────────────

class Message(BaseModel):
    message_id:  str  = Field(default_factory=_uuid)
    from_id:     str                    # agent_id or "engineer"
    to:          str                    # "@agent_name" | "@engineer" | "all"
    content:     str
    type:        str = "chat"           # chat | command | finding | hitl_request | system
    timestamp:   str = Field(default_factory=_now)
    session_id:  str = ""
    metadata:    dict[str, Any] = {}


# ── Finding ───────────────────────────────────────────────────

class Finding(BaseModel):
    finding_id:     str           = Field(default_factory=_uuid)
    host:           str
    port:           Optional[int] = None
    service:        Optional[str] = None
    cve:            Optional[str] = None
    severity:       str                   # CRITICAL | HIGH | MEDIUM | LOW | INFO
    technique_id:   str                   # MITRE ATT&CK e.g. T1021.002
    description:    str
    evidence:       str = ""              # raw output, max 2000 chars
    discovered_by:  str                   # agent_id
    discovered_at:  str = Field(default_factory=_now)
    status:         str = "open"          # open | patched | accepted_risk
    remediation_id: Optional[str] = None


# ── HITL request ─────────────────────────────────────────────

class HitlRequest(BaseModel):
    hitl_id:          str           = Field(default_factory=_uuid)
    requesting_agent: str
    action:           str                   # human-readable description
    risk_level:       str                   # CRITICAL | HIGH | MEDIUM
    context:          str = ""              # Commander-synthesised context
    proposed_command: Optional[str] = None
    target:           Optional[str] = None
    created_at:       str = Field(default_factory=_now)
    status:           str = "pending"       # pending | approved | rejected
    resolved_by:      Optional[str] = None
    resolved_at:      Optional[str] = None
    resolution_note:  Optional[str] = None


# ── Agent registration ────────────────────────────────────────

class AgentRegistration(BaseModel):
    id:              str
    display_name:    str
    icon:            str
    color_hex:       str
    capabilities:    list[str]
    context_profile: list[str]
    status:          str = "ready"
    inbox_channel:   str = ""        # defaults to f"agent.{id}.inbox"

    def model_post_init(self, __context: Any) -> None:
        if not self.inbox_channel:
            self.inbox_channel = f"agent.{self.id}.inbox"


# ── Execution ─────────────────────────────────────────────────

class ExecuteRequest(BaseModel):
    agent_id:    str
    command:     str
    target:      str
    technique:   str        # MITRE ATT&CK ID e.g. T1046
    session_id:  str = ""
    silent:      bool = False  # if True, skip terminal feed broadcast (for internal/housekeeping commands)

class ExecuteResponse(BaseModel):
    execution_id:    str = Field(default_factory=_uuid)
    stdout:          str
    stderr:          str
    exit_code:       int
    scope_validated: bool = True


# ── WebSocket payloads ────────────────────────────────────────

class WsMessage(BaseModel):
    """Generic envelope for all WebSocket messages."""
    type:      str
    timestamp: str = Field(default_factory=_now)
    data:      dict[str, Any] = {}


# ── HITL decision (from dashboard) ───────────────────────────

class HitlDecision(BaseModel):
    hitl_id:  str
    approved: bool
    note:     Optional[str] = None
