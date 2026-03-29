# FILE: agents/remediate/agent.py
"""
Fix Advisor Agent — generates fix packages for confirmed vulnerabilities.

For every finding:
  1. Generate a Fix (Ansible playbook + commands)
  2. Bundle into a ZIP (playbook.yml + INSTRUCTIONS.md + README.md)
  3. Upload ZIP to Command Center — engineer downloads it from the dashboard
  4. NEVER auto-deploy — no credentials assumed, customer applies the fix

High-risk actions (config changes, service restarts) still go through HITL
if the engineer has requested it, but the default output is the ZIP artifact.
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
from fix_generator import Fix, FixType, generate_fix, format_fix_for_hitl, build_fix_zip

logger = logging.getLogger(__name__)

REMEDIATE_INTERVAL = int(os.getenv("REMEDIATE_INTERVAL", "3600"))


class RemediateAgent(BaseAgent):
    AGENT_ID = "remediate-agent"
    CAPABILITIES = [
        "fix_advisory",
        "ansible_playbook_generation",
        "patch_advisory",
        "config_hardening_advisory",
        "fix_package_bundling",
    ]

    SYSTEM_PROMPT = """\
You are the Fix Advisor Agent for SecuNet — an autonomous purple team platform.

Your mission: produce fix packages for confirmed vulnerabilities so engineers can remediate them.
You do NOT deploy fixes — you produce the artifact. The engineer or sysadmin applies it.

Workflow for each finding:
1. Call generate_fix with the vulnerability details — this builds the Ansible playbook and instructions
   and automatically uploads the ZIP package to the Command Center for download.
2. Report back to Commander with a summary of what was packaged.

Prioritise by severity: CRITICAL > HIGH > MEDIUM > LOW.
Be concise in your summaries — Commander decides what to surface to the engineer.
"""

    def tools(self) -> dict:
        return {
            "generate_fix": self._tool_generate_fix,
        }

    # ── Tool implementations ─────────────────────────────────────────────

    async def _tool_generate_fix(self, args: dict) -> str:
        host        = args.get("host", "")
        port        = int(args.get("port", 0) or 0)
        service     = args.get("service", "")
        cve         = args.get("cve", "")
        severity    = args.get("severity", "medium")
        description = args.get("description", "")
        finding_id  = args.get("finding_id", f"{host}_{cve}".replace(":", "-"))

        if not host or not cve:
            return "ERROR: host and cve are required"

        await self.cc.heartbeat(status="running", current_task=f"packaging fix for {cve} on {host}")

        try:
            fix = await generate_fix(
                host=host, port=port, service=service,
                cve=cve, severity=severity, description=description,
            )
        except Exception as exc:
            return f"ERROR generating fix: {exc}"

        # Build and upload ZIP to Command Center
        try:
            zip_bytes = build_fix_zip(fix, host, cve, description)
            uploaded  = await self.cc.upload_fix_package(finding_id, zip_bytes, host=host, cve=cve)
            zip_status = f"ZIP package uploaded ({len(zip_bytes)} bytes)" if uploaded else "ZIP upload failed"
        except Exception as exc:
            zip_status = f"ZIP build failed: {exc}"
            logger.error("[remediate-agent] %s", zip_status)

        logger.info("[remediate-agent] Fix packaged for %s on %s — %s", cve, host, zip_status)

        return (
            f"Fix package ready for {cve} on {host}\n"
            f"Title: {fix.title}\n"
            f"Type: {fix.fix_type.value}\n"
            f"Risk: {fix.estimated_risk.upper()} | Reversible: {'Yes' if fix.reversible else 'No'}\n"
            f"Commands: {len(fix.commands)} | Ansible: {'Yes' if fix.ansible_task else 'No'}\n"
            f"{zip_status}"
        )

    # ── Primary cycle ─────────────────────────────────────────────────────

    async def run_cycle(self) -> None:
        """
        Fix Advisor cycle — woken by Commander tasks via inbox.
        The idle loop just waits; Commander drives all work.
        """
        await self.cc.heartbeat(status="idle", current_task="awaiting tasks from Commander")
        # Sit idle — Commander will push tasks via the Redis inbox whenever
        # a finding needs a fix package generated.
        while self._running:
            await asyncio.sleep(60)
            await self.cc.heartbeat(status="idle", current_task="ready")
