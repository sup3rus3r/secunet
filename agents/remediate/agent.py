# FILE: agents/remediate/agent.py
"""
Remediate Agent — generates and deploys fixes for confirmed vulnerabilities.
ALWAYS requires HITL approval before deploying any fix.
After deployment, notifies @detect to re-verify coverage.
"""
import os
import sys
import asyncio
import json
import logging

_AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
_BASE_DIR  = os.path.join(os.path.dirname(_AGENT_DIR), "base")
for d in (_BASE_DIR, _AGENT_DIR):
    if d not in sys.path:
        sys.path.insert(0, d)

from base_agent import BaseAgent
from fix_generator import Fix, FixType, generate_fix, format_fix_for_hitl

logger = logging.getLogger(__name__)

REMEDIATE_INTERVAL = int(os.getenv("REMEDIATE_INTERVAL", "3600"))


class RemediateAgent(BaseAgent):
    AGENT_ID = "remediate-agent"
    CAPABILITIES = [
        "patch_deployment",
        "config_hardening",
        "firewall_rule",
        "service_hardening",
        "ansible_execution",
    ]

    SYSTEM_PROMPT = """\
You are the Remediate Agent for SecuNet — an autonomous purple team platform.
Your mission: safely patch and harden systems with confirmed vulnerabilities.

CRITICAL RULES — you MUST follow these without exception:
1. NEVER deploy any fix without explicit HITL (Human-in-the-Loop) approval.
2. The workflow is always: generate_fix → request_approval → (only if approved) deploy_fix → verify_fix → notify_detect.
3. If HITL approval is rejected, write a note and move on. Never deploy anyway.
4. Prioritise fixes by severity: CRITICAL > HIGH > MEDIUM > LOW.
5. After deploying a fix, always run verify_fix to confirm it worked.
6. After a successful fix, always notify @detect so they can verify detection coverage is still valid.
7. Log every action clearly. If a fix fails verification, escalate via alert.

You are methodical, precise, and safety-conscious. You operate in production environments.
"""

    def tools(self) -> dict:
        return {
            "generate_fix":     self._tool_generate_fix,
            "request_approval": self._tool_request_approval,
            "deploy_fix":       self._tool_deploy_fix,
            "verify_fix":       self._tool_verify_fix,
            "notify_detect":    self._tool_notify_detect,
        }

    # ── Tool implementations ─────────────────────────────────────────────

    async def _tool_generate_fix(self, args: dict) -> str:
        host        = args.get("host", "")
        port        = int(args.get("port", 0))
        service     = args.get("service", "")
        cve         = args.get("cve", "")
        severity    = args.get("severity", "medium")
        description = args.get("description", "")

        if not host or not cve:
            return "ERROR: host and cve are required"

        await self.cc.heartbeat(status="running", current_task=f"generating fix for {cve} on {host}")

        try:
            fix = await generate_fix(
                host=host,
                port=port,
                service=service,
                cve=cve,
                severity=severity,
                description=description,
            )
        except Exception as exc:
            return f"ERROR generating fix: {exc}"

        # Store fix on instance so request_approval can access it
        fix_key = f"{host}:{cve}"
        if not hasattr(self, "_pending_fixes"):
            self._pending_fixes: dict[str, Fix] = {}
        self._pending_fixes[fix_key] = fix

        summary = format_fix_for_hitl(fix, host, cve)
        return summary

    async def _tool_request_approval(self, args: dict) -> str:
        host        = args.get("host", "")
        cve         = args.get("cve", "")
        fix_summary = args.get("fix_summary", "")
        commands    = args.get("commands", "")

        if not host or not cve:
            return "ERROR: host and cve are required"

        await self.cc.heartbeat(status="waiting_hitl", current_task=f"HITL approval for {cve} on {host}")
        logger.info("[remediate-agent] Requesting HITL approval for %s on %s", cve, host)

        hitl_resp = await self.cc.request_hitl(
            action=f"Deploy remediation fix for {cve}",
            target=host,
            risk_level="HIGH",
            context=fix_summary,
            proposed_command=commands if isinstance(commands, str) else "; ".join(commands),
        )

        hitl_id = hitl_resp.get("hitl_id", "")
        if not hitl_id:
            logger.error("[remediate-agent] HITL request returned no hitl_id")
            return "rejected"

        logger.info("[remediate-agent] Waiting for HITL decision (id=%s)...", hitl_id)
        decision = await self.cc.wait_for_hitl(hitl_id, timeout=3600)
        logger.info("[remediate-agent] HITL decision for %s: %s", cve, decision)
        return decision

    async def _tool_deploy_fix(self, args: dict) -> str:
        host      = args.get("host", "")
        commands  = args.get("commands", [])
        cve       = args.get("cve", "")
        technique = args.get("technique", "T0000")

        if not host:
            return "ERROR: host is required"
        if isinstance(commands, str):
            try:
                commands = json.loads(commands)
            except Exception:
                commands = [commands]
        if not commands:
            return "ERROR: no commands to deploy"

        await self.cc.heartbeat(status="running", current_task=f"deploying fix for {cve} on {host}")
        logger.info("[remediate-agent] Deploying fix for %s on %s (%d commands)", cve, host, len(commands))

        outputs = []
        all_success = True

        for cmd in commands:
            logger.info("[remediate-agent] Executing: %s", cmd[:100])
            result = await self.cc.execute(
                command=cmd,
                target=host,
                technique=technique,
                timeout=300,
            )
            exit_code = result.get("exit_code", -1)
            stdout    = result.get("stdout", "")
            stderr    = result.get("stderr", "")

            status_str = "OK" if exit_code == 0 else f"FAILED (exit {exit_code})"
            outputs.append(f"[{status_str}] {cmd[:80]}")
            if stdout:
                outputs.append(f"  stdout: {stdout[:200]}")
            if stderr and exit_code != 0:
                outputs.append(f"  stderr: {stderr[:200]}")
            if exit_code != 0:
                all_success = False

        combined_output = "\n".join(outputs)

        await self.commander.write_patch_deployed(
            host=host,
            cve=cve,
            action=f"Deployed {len(commands)} fix commands",
            success=all_success,
            output=combined_output[:300],
        )

        status_label = "SUCCESS" if all_success else "PARTIAL FAILURE"
        return f"Deploy {status_label} for {cve} on {host}:\n{combined_output}"

    async def _tool_verify_fix(self, args: dict) -> str:
        host                 = args.get("host", "")
        verification_command = args.get("verification_command", "")
        cve                  = args.get("cve", "")

        if not host:
            return "ERROR: host is required"
        if not verification_command:
            return "No verification command provided — skipping verification"

        await self.cc.heartbeat(status="running", current_task=f"verifying fix for {cve} on {host}")
        logger.info("[remediate-agent] Verifying fix for %s on %s: %s", cve, host, verification_command[:80])

        result = await self.cc.execute(
            command=verification_command,
            target=host,
            technique="T0000",
            timeout=60,
        )

        exit_code = result.get("exit_code", -1)
        stdout    = result.get("stdout", "").strip()
        stderr    = result.get("stderr", "").strip()

        if exit_code == 0:
            return f"VERIFICATION PASSED for {cve} on {host}\nOutput: {stdout[:300]}"
        else:
            msg = f"VERIFICATION FAILED for {cve} on {host} (exit {exit_code})\nstdout: {stdout[:200]}\nstderr: {stderr[:200]}"
            logger.warning("[remediate-agent] %s", msg)
            await self.cc.send_message(
                f"ALERT: Fix verification failed for {cve} on {host}. Manual follow-up required.",
                msg_type="alert",
            )
            return msg

    async def _tool_notify_detect(self, args: dict) -> str:
        host        = args.get("host", "")
        cve         = args.get("cve", "")
        fix_summary = args.get("fix_summary", "")

        if not host or not cve:
            return "ERROR: host and cve are required"

        message = (
            f"Remediation deployed for {cve} on {host}. "
            f"Please re-verify detection coverage is still valid. "
            f"Fix summary: {fix_summary[:300]}"
        )

        await self.cc.send_message(content=message, to="detect-agent", msg_type="task")
        logger.info("[remediate-agent] Notified @detect about fix for %s on %s", cve, host)
        return f"Notified @detect: {message[:100]}"

    # ── Primary cycle ─────────────────────────────────────────────────────

    async def run_cycle(self) -> None:
        """Remediation loop: runs indefinitely on REMEDIATE_INTERVAL."""
        while True:
            try:
                await self._do_remediation_cycle()
            except Exception:
                logger.exception("[remediate-agent] Cycle failed")
            logger.info("[remediate-agent] Cycle complete. Next run in %ds", REMEDIATE_INTERVAL)
            await asyncio.sleep(REMEDIATE_INTERVAL)

    async def _do_remediation_cycle(self) -> None:
        logger.info("[remediate-agent] Starting remediation cycle")
        await self.cc.heartbeat(status="running", current_task="querying open vulnerabilities")

        # 1. Query Commander for open vulnerabilities that need remediation
        context = await self.commander.ask(
            "List all open vulnerability findings that have not been remediated. "
            "Include host, port, service, CVE, severity, and description for each. "
            "Prioritize by severity (CRITICAL first, then HIGH, MEDIUM, LOW). "
            "Exclude any vulnerabilities where patch_deployed events already exist."
        )

        if not context or "no " in context.lower()[:50] and "vulnerabilit" in context.lower():
            logger.info("[remediate-agent] No open vulnerabilities to remediate")
            await self.cc.heartbeat(status="idle", current_task="no open vulnerabilities")
            return

        await self.cc.send_message(
            f"Remediation cycle started. Reviewing open vulnerabilities:\n{context[:400]}"
        )

        # 2. Ask the LLM to prioritise and plan remediations
        prompt = f"""OPEN VULNERABILITIES FROM COMMANDER:
{context}

Your task:
1. Identify the highest-priority vulnerabilities to fix (CRITICAL/HIGH first).
2. For each vulnerability, call generate_fix to produce a remediation plan.
3. Then call request_approval to get HITL sign-off.
4. If approved, call deploy_fix with the commands from the fix.
5. Call verify_fix to confirm the fix worked.
6. Call notify_detect so they can re-check detection coverage.
7. If a HITL request is rejected, skip that vulnerability and note it.

Work through vulnerabilities one at a time. Be systematic.
"""

        result = await self.think_and_act(prompt, max_tokens=4096)

        # 3. Broadcast summary
        await self.cc.send_message(
            f"Remediation cycle complete.\n\n{result[:600]}"
        )
        logger.info("[remediate-agent] Remediation cycle complete")

    # ── Inbox message handler ────────────────────────────────────────────

    async def _handle_inbox(self, message: dict) -> None:
        """
        Handle incoming messages. Detect agent may send messages about
        undetected techniques that need a detection rule or config hardening.
        """
        content = message.get("content", "")
        sender  = message.get("from_id", "unknown")

        if not content:
            return

        logger.info("[remediate-agent] Inbox from %s: %s", sender, content[:80])

        # Check if this is a detection gap notification from @detect
        if "detect" in sender.lower() and (
            "undetected" in content.lower() or
            "detection gap" in content.lower() or
            "rule" in content.lower()
        ):
            context = await self.commander.ask(
                f"What hardening or config changes could help improve detection for: {content}"
            )
            prompt = (
                f"MESSAGE FROM {sender.upper()} (Detection Gap Notice):\n{content}\n\n"
                f"CONTEXT:\n{context}\n\n"
                "Assess whether a config hardening fix can help close this detection gap. "
                "If so, generate a fix and request HITL approval before deploying anything."
            )
        else:
            context = await self.commander.ask(content)
            prompt = f"MESSAGE FROM {sender.upper()}: {content}\n\nCONTEXT:\n{context}"

        try:
            reply = await self.think_and_act(prompt, max_tokens=4096)
        except Exception as exc:
            reply = f"[remediate-agent] Error processing message: {exc}"

        await self.cc.send_message(reply, to=sender)
