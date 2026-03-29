"""
Command Center HTTP client.
All agents use this to talk to the CC REST API.
"""
import os
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

CC_URL     = os.getenv("CC_URL", "http://command-center:8001")
CC_TIMEOUT = float(os.getenv("CC_TIMEOUT", "30"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CCClient:
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self._http    = httpx.AsyncClient(base_url=CC_URL, timeout=CC_TIMEOUT)

    # ── Agent lifecycle ───────────────────────────────────────────────────

    async def register(
        self,
        display_name: str,
        icon: str,
        color_hex: str,
        capabilities: list[str],
        context_profile: list[str],
    ) -> bool:
        try:
            r = await self._http.post("/agents/register", json={
                "id":              self.agent_id,
                "display_name":    display_name,
                "icon":            icon,
                "color_hex":       color_hex,
                "capabilities":    capabilities,
                "context_profile": context_profile,
                "status":          "online",
            })
            r.raise_for_status()
            logger.info("[%s] Registered with CC", self.agent_id)
            return True
        except Exception as exc:
            logger.error("[%s] Registration failed: %s", self.agent_id, exc)
            return False

    async def heartbeat(self, status: str = "online", current_task: str | None = None) -> None:
        try:
            payload: dict[str, Any] = {"status": status}
            if current_task is not None:
                payload["current_task"] = current_task
            await self._http.post(f"/agents/{self.agent_id}/heartbeat", json=payload)
        except Exception as exc:
            logger.debug("[%s] Heartbeat failed: %s", self.agent_id, exc)

    # ── Execution ─────────────────────────────────────────────────────────

    async def execute(
        self,
        command: str,
        target: str,
        technique: str = "T0000",
        timeout: int = 300,
        silent: bool = False,
    ) -> dict[str, Any]:
        """
        Request the CC OS layer to run a command against a scoped target.
        Returns {"stdout": ..., "stderr": ..., "exit_code": ...} or error dict.
        silent=True skips terminal feed broadcast (for internal housekeeping commands).
        """
        try:
            r = await self._http.post("/execute", json={
                "agent_id":  self.agent_id,
                "command":   command,
                "target":    target,
                "technique": technique,
                "silent":    silent,
            }, timeout=timeout + 10)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as exc:
            logger.error("[%s] Execute HTTP %s: %s", self.agent_id,
                         exc.response.status_code, exc.response.text[:200])
            return {"stdout": "", "stderr": str(exc), "exit_code": -1}
        except Exception as exc:
            logger.error("[%s] Execute failed: %s", self.agent_id, exc)
            return {"stdout": "", "stderr": str(exc), "exit_code": -1}

    # ── Messaging ─────────────────────────────────────────────────────────

    async def send_message(self, content: str, to: str = "broadcast",
                           msg_type: str = "chat") -> None:
        try:
            await self._http.post("/messages/send", json={
                "message_id": str(uuid.uuid4()),
                "from_id":    self.agent_id,
                "to":         to,
                "content":    content,
                "type":       msg_type,
                "timestamp":  _now(),
            })
        except Exception as exc:
            logger.debug("[%s] send_message failed: %s", self.agent_id, exc)

    # ── Mission state ─────────────────────────────────────────────────────

    async def get_target_scope(self) -> str:
        """Fetch the live target scope from CC mission state."""
        try:
            r = await self._http.get("/mission/state")
            r.raise_for_status()
            return r.json().get("target_scope", "")
        except Exception as exc:
            logger.error("[%s] get_target_scope failed: %s", self.agent_id, exc)
            return ""

    # ── Commander context ─────────────────────────────────────────────────

    async def query_commander(self, query: str) -> str:
        try:
            r = await self._http.post("/commander/query", json={
                "agent_id": self.agent_id,
                "query":    query,
            })
            r.raise_for_status()
            return r.json().get("context", "")
        except Exception as exc:
            logger.error("[%s] Commander query failed: %s", self.agent_id, exc)
            return ""

    async def write_event(self, event_type: str, payload: dict[str, Any]) -> None:
        try:
            await self._http.post("/commander/write", json={
                **payload,
                "event_type": event_type,
                "agent_id":   self.agent_id,
                "timestamp":  payload.get("timestamp", _now()),
            })
        except Exception as exc:
            logger.debug("[%s] write_event failed: %s", self.agent_id, exc)

    # ── HITL ──────────────────────────────────────────────────────────────

    async def request_hitl(
        self,
        action: str,
        target: str,
        risk_level: str = "HIGH",
        context: str = "",
        proposed_command: str | None = None,
    ) -> dict[str, Any]:
        """
        Submit a HITL approval request.
        Returns the CC response dict including hitl_id.
        """
        try:
            r = await self._http.post("/hitl", json={
                "requesting_agent": self.agent_id,
                "action":           action,
                "target":           target,
                "risk_level":       risk_level,
                "context":          context,
                "proposed_command": proposed_command,
            })
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            logger.error("[%s] HITL request failed: %s", self.agent_id, exc)
            return {}

    async def wait_for_hitl(self, hitl_id: str, timeout: int = 300) -> str:
        """
        Poll for HITL resolution. Returns 'approved' or 'rejected'.
        """
        import asyncio
        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            try:
                r = await self._http.get(f"/hitl/{hitl_id}")
                if r.status_code == 200:
                    data = r.json()
                    status = data.get("status", "pending")
                    if status in ("approved", "rejected"):
                        return status
            except Exception:
                pass
            await asyncio.sleep(5)
        return "rejected"  # timeout = reject

    async def aclose(self) -> None:
        await self._http.aclose()
