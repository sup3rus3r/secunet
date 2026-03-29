# FILE: agents/detect/agent.py
"""
Detect Agent — measures detection coverage for every technique the Exploit Agent runs.
Queries all configured SIEMs for evidence of alerts.
Generates Sigma rules for undetected techniques.
Scores coverage 0-100 and broadcasts to mission state.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sys

# Allow importing from base/
_AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
_BASE_DIR  = os.path.join(os.path.dirname(_AGENT_DIR), "base")
for d in (_BASE_DIR, _AGENT_DIR):
    if d not in sys.path:
        sys.path.insert(0, d)

from base_agent import BaseAgent
from sigma_generator import generate_sigma_rule, validate_sigma_rule
from siem import get_available_siem_clients

logger = logging.getLogger(__name__)

DETECT_INTERVAL = int(os.getenv("DETECT_INTERVAL", "900"))  # seconds between cycles


class DetectAgent(BaseAgent):
    AGENT_ID     = "detect-agent"
    CAPABILITIES = [
        "siem_query",
        "detection_scoring",
        "sigma_generation",
        "coverage_analysis",
        "alert_triage",
    ]

    SYSTEM_PROMPT = """You are the Detect Agent for SecuNet — an autonomous purple team platform.

Your mission: measure the detection coverage of the organisation's SIEM stack against every
offensive technique that the Exploit Agent exercises.

You:
- Query all configured SIEMs (Splunk, Elastic, Microsoft Sentinel) for evidence of alerts
  fired against each technique.
- Score each technique: 100 = fully detected, 50 = partial detection (some SIEMs missed it),
  0 = completely missed by all SIEMs.
- Calculate and broadcast an overall coverage score (average across all techniques).
- For every undetected technique, generate a Sigma detection rule to fill the gap and write
  it to Commander as a high-priority finding.
- Triage and summarise alerts to help the security team understand what was caught and what
  was missed.

You are the defender's measurement instrument. Be precise, methodical, and comprehensive.
Every technique the red side runs must be accounted for.

When you use tools, call them with the exact argument schemas described in Available tools.
After completing a cycle, provide a clear written summary of coverage gaps and new Sigma rules."""

    # ── Tools ─────────────────────────────────────────────────────────────

    def tools(self) -> dict:
        return {
            "query_siem":            self._tool_query_siem,
            "score_technique":       self._tool_score_technique,
            "generate_sigma":        self._tool_generate_sigma,
            "update_coverage_score": self._tool_update_coverage_score,
        }

    async def _tool_query_siem(self, args: dict) -> str:
        """
        Query all available SIEM clients for a technique and return aggregated results.
        args: {technique_id, host}
        """
        technique_id = args.get("technique_id", "")
        host         = args.get("host") or None

        if not technique_id:
            return "ERROR: technique_id required"

        clients = get_available_siem_clients()
        if not clients:
            return (
                f"No SIEM clients configured. Cannot check coverage for {technique_id}. "
                "Scoring as 0 (undetected)."
            )

        await self.cc.heartbeat(
            status="running",
            current_task=f"SIEM query {technique_id}",
        )

        all_results: list[dict] = []
        for client in clients:
            name = type(client).__name__
            try:
                result = await client.check_technique(technique_id, host=host)
                result["siem_name"] = name
                all_results.append(result)
                logger.info(
                    "[detect-agent] %s: %s detected=%s alerts=%d",
                    name, technique_id, result["detected"], result["alert_count"],
                )
            except Exception as exc:
                logger.error("[detect-agent] %s query failed: %s", name, exc)
                all_results.append({
                    "siem_name":   name,
                    "detected":    False,
                    "alert_count": 0,
                    "events":      [],
                    "query_used":  "",
                    "error":       str(exc),
                })

        total_alerts = sum(r["alert_count"] for r in all_results)
        detected_by  = [r["siem_name"] for r in all_results if r["detected"]]
        missed_by    = [r["siem_name"] for r in all_results if not r["detected"]]

        lines = [
            f"SIEM query results for technique {technique_id}" +
            (f" on host {host}" if host else ""),
            f"Total alerts across all SIEMs: {total_alerts}",
            f"Detected by:  {', '.join(detected_by) or 'none'}",
            f"Missed by:    {', '.join(missed_by) or 'none'}",
        ]
        for r in all_results:
            lines.append(
                f"\n[{r['siem_name']}]"
                f" detected={r['detected']}"
                f" alerts={r['alert_count']}"
                + (f" error={r['error']}" if r.get('error') else "")
            )
            if r.get("events"):
                lines.append(f"  Sample event: {json.dumps(r['events'][0])[:200]}")

        return "\n".join(lines)

    async def _tool_score_technique(self, args: dict) -> str:
        """
        Calculate a 0-100 detection score for a technique and write to Commander.
        args: {technique_id, detected, alert_count}
        """
        technique_id = args.get("technique_id", "")
        detected     = bool(args.get("detected", False))
        alert_count  = int(args.get("alert_count", 0))

        if not technique_id:
            return "ERROR: technique_id required"

        # Scoring logic:
        # - Fully detected (alert_count >= 2): 100
        # - Partially detected (detected=True, alert_count=1): 75
        # - Detected flag True but alert_count=0: 50 (edge case — rule fired but no events)
        # - Not detected: 0
        if detected and alert_count >= 2:
            score = 100.0
            label = "fully detected"
        elif detected and alert_count == 1:
            score = 75.0
            label = "detected (single alert)"
        elif detected:
            score = 50.0
            label = "partial detection (no event details)"
        else:
            score = 0.0
            label = "undetected"

        await self.commander.write_detection_score(
            technique=technique_id,
            score=score,
            alert_triggered=detected,
            siem="all_configured",
            rule_matched="",
        )

        return (
            f"Technique {technique_id}: score={score}/100 ({label}). "
            f"Alert count: {alert_count}. Written to Commander."
        )

    async def _tool_generate_sigma(self, args: dict) -> str:
        """
        Generate a Sigma rule for an undetected technique.
        args: {technique_id, technique_name, context}
        """
        technique_id   = args.get("technique_id", "")
        technique_name = args.get("technique_name", technique_id)
        context        = args.get("context", "")

        if not technique_id:
            return "ERROR: technique_id required"

        await self.cc.heartbeat(
            status="running",
            current_task=f"sigma generation {technique_id}",
        )

        yaml_text = await generate_sigma_rule(
            technique_id=technique_id,
            technique_name=technique_name,
            context=context,
        )

        if not yaml_text:
            return f"ERROR: LLM failed to generate Sigma rule for {technique_id}"

        is_valid, error = validate_sigma_rule(yaml_text)
        if not is_valid:
            logger.warning(
                "[detect-agent] Generated Sigma rule for %s failed validation: %s",
                technique_id, error,
            )
            # Still return the rule — the engineer can fix it
            return (
                f"WARNING: Generated rule failed validation ({error}).\n"
                f"Rule YAML (may need manual fixes):\n\n{yaml_text}"
            )

        # Write to Commander as a finding
        await self.commander.write_vulnerability(
            host="N/A",
            port=0,
            service="SIEM",
            cve=f"SIGMA-{technique_id}",
            cvss=5.0,
            severity="medium",
            title=f"Missing detection rule for {technique_id} ({technique_name})",
            description=(
                f"Technique {technique_id} ({technique_name}) was exercised but not detected "
                f"by any configured SIEM. A Sigma rule has been generated. "
                f"Deploy to SIEM to close the coverage gap."
            ),
            technique=technique_id,
        )

        logger.info("[detect-agent] Sigma rule generated and written for %s", technique_id)
        return f"Sigma rule generated for {technique_id} (valid).\n\n{yaml_text}"

    async def _tool_update_coverage_score(self, args: dict) -> str:
        """
        Broadcast the overall coverage score to the mission state.
        args: {score}  (0.0 – 100.0)
        """
        score = float(args.get("score", 0.0))
        score = max(0.0, min(100.0, score))

        await self.cc.write_event(
            "mission.metric",
            {"field": "coverage_score", "value": score},
        )

        await self.cc.send_message(
            f"Detection coverage score updated: {score:.1f}/100"
        )

        return f"Coverage score {score:.1f}/100 written to mission state."

    # ── Inbox override ────────────────────────────────────────────────────

    async def _handle_inbox(self, message: dict) -> None:
        """
        Handle messages from @exploit (technique notification) and others.
        When Exploit notifies us of a new technique, trigger an immediate check.
        """
        content = message.get("content", "")
        sender  = message.get("from_id", "unknown")

        if not content:
            return

        logger.info("[detect-agent] Inbox from %s: %s", sender, content[:120])

        # Try to parse a technique ID from the message
        technique_match = re.search(r"\bT\d{4}(?:\.\d{3})?\b", content)

        if technique_match and sender == "exploit-agent":
            technique_id = technique_match.group()
            logger.info(
                "[detect-agent] Exploit notification: checking technique %s immediately",
                technique_id,
            )
            # Extract host if present
            host_match = re.search(
                r"\b(?:target|host)[\s:]+(\d{1,3}(?:\.\d{1,3}){3})", content, re.IGNORECASE
            )
            host = host_match.group(1) if host_match else None

            asyncio.create_task(
                self._check_and_score_technique(
                    technique_id=technique_id,
                    host=host,
                    context=content,
                )
            )
            await self.cc.send_message(
                f"Received technique notification for {technique_id}. "
                "Querying SIEMs now.",
                to=sender,
            )
        else:
            # Generic message — standard LLM handler
            await super()._handle_inbox(message)

    # ── Internal helpers ──────────────────────────────────────────────────

    async def _check_and_score_technique(
        self,
        technique_id: str,
        host:         str | None = None,
        context:      str = "",
        technique_name: str = "",
    ) -> dict:
        """
        Full pipeline for a single technique: query → score → generate Sigma if missed.

        Returns a summary dict for the caller.
        """
        clients = get_available_siem_clients()
        if not clients:
            await self.commander.write_detection_score(
                technique=technique_id, score=0.0,
                alert_triggered=False, siem="none_configured",
            )
            return {"technique_id": technique_id, "score": 0.0, "detected": False}

        total_alerts   = 0
        siem_detected  = 0

        for client in clients:
            name = type(client).__name__
            try:
                result = await client.check_technique(technique_id, host=host)
                if result["detected"]:
                    siem_detected += 1
                total_alerts += result["alert_count"]
            except Exception as exc:
                logger.error("[detect-agent] %s check failed: %s", name, exc)

        detected = siem_detected > 0
        n_siems  = len(clients)

        if siem_detected == n_siems:
            score = 100.0
        elif siem_detected > 0:
            score = round((siem_detected / n_siems) * 100.0, 1)
        else:
            score = 0.0

        await self.commander.write_detection_score(
            technique=technique_id,
            score=score,
            alert_triggered=detected,
            siem="all_configured",
        )

        # Generate Sigma rule for undetected techniques
        if not detected:
            logger.info(
                "[detect-agent] %s undetected — generating Sigma rule", technique_id
            )
            name = technique_name or technique_id
            yaml_text = await generate_sigma_rule(
                technique_id=technique_id,
                technique_name=name,
                context=context,
            )
            if yaml_text:
                is_valid, _ = validate_sigma_rule(yaml_text)
                await self.commander.write_vulnerability(
                    host="N/A",
                    port=0,
                    service="SIEM",
                    cve=f"SIGMA-{technique_id}",
                    cvss=5.0,
                    severity="medium",
                    title=f"Missing detection rule for {technique_id} ({name})",
                    description=(
                        f"No SIEM detected {technique_id}. Sigma rule generated "
                        f"({'valid' if is_valid else 'needs review'}).\n\n{yaml_text[:400]}"
                    ),
                    technique=technique_id,
                )

        return {
            "technique_id": technique_id,
            "score":        score,
            "detected":     detected,
            "alert_count":  total_alerts,
        }

    # ── Primary cycle ─────────────────────────────────────────────────────

    async def run_cycle(self) -> None:
        """
        Main autonomous detection cycle — runs indefinitely on DETECT_INTERVAL.
        Each cycle:
        1. Query Commander for recent exploit attempts.
        2. For each unique technique, query all SIEMs.
        3. Score each technique.
        4. Calculate overall coverage score.
        5. Write scores and Sigma rules to Commander.
        6. Broadcast updated coverage score.
        """
        while True:
            try:
                await self._do_detect_cycle()
            except Exception:
                logger.exception("[detect-agent] Cycle failed")

            logger.info(
                "[detect-agent] Cycle complete. Next run in %ds", DETECT_INTERVAL
            )
            await asyncio.sleep(DETECT_INTERVAL)

    async def _do_detect_cycle(self) -> None:
        logger.info("[detect-agent] Starting detection cycle")

        # 1. Get recent exploit attempts from Commander
        context = await self.commander.ask(
            "List all exploit_attempt events from the last cycle. "
            "For each, include: host, port, CVE, technique ID (MITRE ATT&CK), "
            "module name, outcome (success/failed). "
            "Also include any command_execution events if available."
        )

        if not context or "no exploit" in context.lower():
            logger.info("[detect-agent] No exploit attempts found in Commander context")
            await self.cc.send_message(
                "Detect cycle: no recent exploit attempts found. "
                "Waiting for Exploit Agent activity."
            )
            return

        await self.cc.heartbeat(status="running", current_task="detection scoring cycle")

        # 2. Use LLM to extract techniques and drive SIEM queries
        prompt = f"""RECENT EXPLOIT ATTEMPTS FROM COMMANDER:
{context}

You are the Detect Agent. For each exploit attempt above:
1. Use `query_siem` to check all SIEMs for evidence that the technique was detected.
   Pass the technique_id (MITRE ATT&CK T-number) and the target host.
2. Use `score_technique` to record the detection score (0-100).
3. If a technique scored 0 (undetected), use `generate_sigma` to create a detection rule.

After processing all techniques, use `update_coverage_score` with the average score
across all techniques evaluated this cycle.

Be systematic: cover every unique technique_id found in the data above."""

        result = await self.think_and_act(prompt, max_tokens=4096)

        # 3. Broadcast summary
        await self.cc.send_message(
            f"Detection cycle complete.\n\n{result[:700]}"
        )

        logger.info("[detect-agent] Detection cycle done")
