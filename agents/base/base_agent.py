"""
BaseAgent — the foundation every SecuNet agent inherits from.

Handles:
  - Registration with CC on startup
  - Heartbeat loop (every 30s)
  - Redis inbox subscription + message dispatch
  - LLM loop: builds prompt from Commander context, calls LLM, executes tools
  - Graceful shutdown

Subclasses implement:
  - AGENT_ID       : str
  - CAPABILITIES   : list[str]
  - SYSTEM_PROMPT  : str
  - tools()        : dict[str, callable]  — tool_name -> async fn(args) -> str
  - run_cycle()    : the agent's primary autonomous work loop
"""
import os
import sys
import json
import asyncio
import logging
import uuid
from datetime import datetime, timezone

# Allow importing cc_client / commander_client from base/
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if _BASE_DIR not in sys.path:
    sys.path.insert(0, _BASE_DIR)

from cc_client import CCClient
from commander_client import CommanderClient

logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", "30"))
LLM_PROVIDER       = os.getenv("LLM_PROVIDER", "anthropic").lower()
CC_URL             = os.getenv("CC_URL", "http://command-center:8001")

# Resolve model: LLM_MODEL overrides everything; otherwise use provider-specific var
_PROVIDER_MODEL_ENV = {
    "anthropic": ("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
    "openai":    ("OPENAI_MODEL",     "gpt-4o"),
    "lmstudio":  ("LMSTUDIO_MODEL",   "local-model"),
    "fireworks": ("FIREWORKS_MODEL",  "accounts/fireworks/models/llama-v3p1-70b-instruct"),
}
_env_var, _default = _PROVIDER_MODEL_ENV.get(LLM_PROVIDER, ("ANTHROPIC_MODEL", "claude-sonnet-4-6"))
LLM_MODEL = os.getenv("LLM_MODEL") or os.getenv(_env_var, _default)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── LLM abstraction (mirrors command-center/llm_client.py) ───────────────────

async def _llm_complete(system: str, messages: list[dict],
                        max_tokens: int = 4096, model: str | None = None) -> str:
    _model = model or LLM_MODEL
    if LLM_PROVIDER == "anthropic":
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
        resp = await client.messages.create(
            model=_model, max_tokens=max_tokens,
            system=system, messages=messages,
        )
        return resp.content[0].text
    elif LLM_PROVIDER in ("openai", "lmstudio", "fireworks"):
        from openai import AsyncOpenAI
        if LLM_PROVIDER == "lmstudio":
            kwargs = {
                "api_key":  os.getenv("OPENAI_API_KEY", "none"),
                "base_url": os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1"),
            }
        elif LLM_PROVIDER == "fireworks":
            kwargs = {
                "api_key":  os.getenv("FIREWORKS_API_KEY", "none"),
                "base_url": os.getenv("FIREWORKS_BASE_URL", "https://api.fireworks.ai/inference/v1"),
            }
        else:
            kwargs = {"api_key": os.getenv("OPENAI_API_KEY", "none")}
        client = AsyncOpenAI(**kwargs)
        full = [{"role": "system", "content": system}] + messages
        resp = await client.chat.completions.create(
            model=_model, max_tokens=max_tokens, messages=full,
        )
        return resp.choices[0].message.content
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {LLM_PROVIDER!r}. Must be anthropic, openai, lmstudio, or fireworks.")


# ── Tool-call parsing (simple JSON block extraction) ─────────────────────────

def _parse_tool_calls(text: str) -> list[dict]:
    """
    Extract tool calls from LLM output.
    Expected format (anywhere in output):
      ```tool
      {"name": "nmap_scan", "args": {"target": "10.0.0.0/24"}}
      ```
    Returns list of {"name": ..., "args": ...} dicts.
    """
    calls = []
    import re
    pattern = r"```tool\s*\n(.*?)\n```"
    for match in re.finditer(pattern, text, re.DOTALL):
        try:
            obj = json.loads(match.group(1).strip())
            if "name" in obj:
                calls.append(obj)
        except json.JSONDecodeError:
            pass
    return calls


# ── Base class ────────────────────────────────────────────────────────────────

class BaseAgent:
    AGENT_ID:      str = "base-agent"
    CAPABILITIES:  list[str] = []
    SYSTEM_PROMPT: str = "You are a SecuNet agent."

    def __init__(self):
        self.cc        = CCClient(self.AGENT_ID)
        self.commander = CommanderClient(self.cc)
        self._running  = False
        self._tasks: list[asyncio.Task] = []

    # ── Subclass interface ────────────────────────────────────────────────

    def tools(self) -> dict:
        """Return dict of tool_name -> async callable(args: dict) -> str."""
        return {}

    async def run_cycle(self) -> None:
        """
        Primary autonomous work loop. Called once per cycle after startup.
        Subclasses must implement this.
        """
        raise NotImplementedError

    # ── LLM call with tool execution ──────────────────────────────────────

    async def think_and_act(
        self,
        user_prompt: str,
        max_tokens: int = 4096,
        model: str | None = None,
    ) -> str:
        """
        Send a prompt to the LLM (with tool support).
        If the LLM emits tool calls, execute them and feed results back.
        Returns the final LLM text response.
        """
        available_tools = self.tools()
        tool_docs = "\n".join(
            f"  - {name}" for name in available_tools
        ) if available_tools else "  (none)"

        system = (
            f"{self.SYSTEM_PROMPT}\n\n"
            f"Available tools:\n{tool_docs}\n\n"
            "To call a tool, output a fenced code block:\n"
            "```tool\n"
            '{"name": "tool_name", "args": {"key": "value"}}\n'
            "```\n"
            "You may call multiple tools. After tool results are provided, "
            "give your final analysis."
        )

        messages = [{"role": "user", "content": user_prompt}]
        max_rounds = 5

        for _ in range(max_rounds):
            text = await _llm_complete(system, messages, max_tokens, model)
            calls = _parse_tool_calls(text)

            if not calls:
                return text  # no tools called — final answer

            # Append assistant turn
            messages.append({"role": "assistant", "content": text})

            # Execute tools and collect results
            results = []
            for call in calls:
                tool_fn = available_tools.get(call["name"])
                if tool_fn:
                    try:
                        result = await tool_fn(call.get("args", {}))
                    except Exception as exc:
                        result = f"ERROR: {exc}"
                else:
                    result = f"Unknown tool: {call['name']}"
                results.append(f"[{call['name']}]\n{result}")

            tool_result_msg = "\n\n".join(results)
            messages.append({"role": "user", "content": f"Tool results:\n{tool_result_msg}"})

        # Hit max rounds — return last response
        return text

    # ── Inbox handler ─────────────────────────────────────────────────────

    async def _handle_inbox(self, message: dict) -> None:
        """
        Process a message from the Redis inbox.
        Only Commander is authorised to task agents — all other senders are ignored.
        Results are always reported back to Commander only.
        """
        content = message.get("content", "")
        sender  = message.get("from_id", "unknown")
        msg_type = message.get("type", "task")

        if not content:
            return

        # HARD RULE: only Commander can task an agent
        if sender != "commander":
            logger.debug("[%s] Ignoring message from %s — not Commander", self.AGENT_ID, sender)
            return

        logger.info("[%s] Task from Commander: %s", self.AGENT_ID, content[:80])

        context = await self.commander.ask(content)
        prompt  = (
            f"TASK FROM COMMANDER: {content}\n\n"
            f"MISSION CONTEXT:\n{context}"
        )

        try:
            reply = await self.think_and_act(prompt, max_tokens=4096)
        except Exception as exc:
            reply = f"[{self.AGENT_ID}] Error: {exc}"

        # Report result back to Commander only — never broadcast, never reply to sender
        await self.cc.send_message(reply, to="commander", msg_type="result")

    # ── Mission control polling ───────────────────────────────────────────

    async def check_mission_control(self) -> str:
        """
        Poll CC for mission directives. Returns: 'run' | 'pause' | 'kill' | 'force-hitl'.
        Agents call this at the top of their run_cycle loop.
        """
        try:
            import httpx
            async with httpx.AsyncClient(base_url=CC_URL, timeout=5) as client:
                r = await client.get("/mission/control")
                if r.status_code == 200:
                    return r.json().get("directive", "run")
        except Exception:
            pass
        return "run"

    # ── Heartbeat loop ────────────────────────────────────────────────────

    async def _heartbeat_loop(self) -> None:
        while self._running:
            # Check mission directive on every heartbeat
            directive = await self.check_mission_control()
            if directive == "kill":
                logger.warning("[%s] KILL directive received — shutting down", self.AGENT_ID)
                await self.cc.heartbeat(status="offline")
                await self.stop()
                return
            status = "paused" if directive == "pause" else "online"
            await self.cc.heartbeat(status=status)
            await asyncio.sleep(HEARTBEAT_INTERVAL)

    # ── Startup / shutdown ────────────────────────────────────────────────

    async def start(self) -> None:
        """Register, subscribe to inbox, start heartbeat, then run cycle."""
        self._running = True
        logger.info("[%s] Starting...", self.AGENT_ID)

        # Register (retry until CC is reachable)
        meta = AGENT_META.get(self.AGENT_ID, {})
        for attempt in range(10):
            if await self.cc.register(
                display_name=meta.get("display_name", self.AGENT_ID),
                icon=meta.get("icon", "server"),
                color_hex=meta.get("color_hex", "#5A6A7E"),
                capabilities=self.CAPABILITIES,
                context_profile=meta.get("context_profile", []),
            ):
                break
            wait = min(2 ** attempt, 30)
            logger.warning("[%s] Registration failed, retry in %ds", self.AGENT_ID, wait)
            await asyncio.sleep(wait)

        # Subscribe to inbox via Redis
        try:
            import redis.asyncio as aioredis
            redis_url = os.getenv("REDIS_URL", "redis://redis:6379")
            r = aioredis.from_url(redis_url, decode_responses=True)
            inbox_channel = f"agent.{self.AGENT_ID.replace('-agent', '')}.inbox"

            async def _redis_listener():
                async with r.pubsub() as ps:
                    await ps.subscribe(inbox_channel)
                    logger.info("[%s] Subscribed to %s", self.AGENT_ID, inbox_channel)
                    async for raw in ps.listen():
                        if raw["type"] != "message":
                            continue
                        try:
                            msg = json.loads(raw["data"])
                            asyncio.create_task(self._handle_inbox(msg))
                        except Exception:
                            logger.exception("[%s] Inbox parse error", self.AGENT_ID)

            self._tasks.append(asyncio.create_task(_redis_listener()))
        except Exception as exc:
            logger.error("[%s] Redis inbox setup failed: %s", self.AGENT_ID, exc)

        # Heartbeat
        self._tasks.append(asyncio.create_task(self._heartbeat_loop()))

        # Notify Commander of readiness — no broadcast
        await self.cc.send_message(
            f"{self.AGENT_ID} online. Capabilities: {', '.join(self.CAPABILITIES)}",
            to="commander",
            msg_type="status",
        )

        # Primary work loop
        try:
            await self.run_cycle()
        except Exception:
            logger.exception("[%s] run_cycle crashed", self.AGENT_ID)
        finally:
            await self.stop()

    async def stop(self) -> None:
        self._running = False
        for t in self._tasks:
            t.cancel()
        await self.cc.aclose()
        logger.info("[%s] Stopped", self.AGENT_ID)


# Per-agent registration metadata — subclasses set these
AGENT_META: dict[str, dict] = {
    "recon-agent": {
        "display_name":    "Recon",
        "icon":            "eye",
        "color_hex":       "#00D4FF",
        "context_profile": ["scan_result", "asset_discovery", "service_fingerprint", "summary", "message"],
    },
    "exploit-agent": {
        "display_name":    "Exploit",
        "icon":            "server",
        "color_hex":       "#FF3B30",
        "context_profile": ["scan_result", "vulnerability_finding", "credential_found",
                            "exploit_attempt", "access_path", "summary", "message"],
    },
    "detect-agent": {
        "display_name":    "Detect",
        "icon":            "shield",
        "color_hex":       "#FFB300",
        "context_profile": ["exploit_attempt", "command_execution", "detection_score",
                            "alert_result", "summary", "message"],
    },
    "remediate-agent": {
        "display_name":    "Remediate",
        "icon":            "wrench",
        "color_hex":       "#00C851",
        "context_profile": ["vulnerability_finding", "detection_score", "patch_deployed",
                            "hitl_approval", "summary", "message"],
    },
    "monitor-agent": {
        "display_name":    "Monitor",
        "icon":            "monitor",
        "color_hex":       "#9B59B6",
        "context_profile": ["asset_discovery", "patch_deployed", "vulnerability_finding",
                            "anomaly_event", "tripwire_state", "summary"],
    },
}
