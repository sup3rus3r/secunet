# FILE: agents/monitor/agent.py
"""
Monitor Agent — continuous 24/7 surveillance of the target environment.
Watches for changes, deploys tripwires, detects anomalies.
Reports to @exploit for new attack surface, @engineer for critical events.
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
from tripwire_deployer import (
    TripwireType,
    create_honeytoken_file,
    create_fake_credential,
    create_canary_listener,
    create_audit_rule,
    get_tripwires_for_host,
    all_tripwires,
    DEPLOYED,
)
from anomaly_detector import AnomalyDetector, AnomalyType

logger = logging.getLogger(__name__)

MONITOR_INTERVAL = int(os.getenv("MONITOR_INTERVAL", "300"))   # 5 minutes


class MonitorAgent(BaseAgent):
    AGENT_ID = "monitor-agent"
    CAPABILITIES = [
        "continuous_monitoring",
        "tripwire_deployment",
        "anomaly_detection",
        "asset_tracking",
        "change_detection",
    ]

    SYSTEM_PROMPT = """\
You are the Monitor Agent for SecuNet — an autonomous purple team platform.
Your mission: continuous, uninterrupted surveillance of every known asset.

You are ALWAYS watching. Your responsibilities:
- Detect changes in open ports or service versions on known hosts immediately.
- Deploy tripwires (honeytokens, canary listeners, audit rules) on newly discovered assets.
- Check all deployed tripwires every cycle for signs of access or activation.
- Sweep the target scope for new hosts that have appeared since the last cycle.
- Report anomalies to Commander and alert engineers for high/critical severity events.
- Notify @recon when new hosts appear so a full scan can be performed.
- Notify @exploit when new open ports or services are detected (potential new attack surface).

NEVER stop monitoring. Operate continuously on the MONITOR_INTERVAL.
Be concise in summaries — speed matters. Flag everything suspicious.
"""

    def __init__(self):
        super().__init__()
        self._detector = AnomalyDetector()

    def tools(self) -> dict:
        return {
            "check_host_changes":  self._tool_check_host_changes,
            "deploy_tripwire":     self._tool_deploy_tripwire,
            "check_tripwires":     self._tool_check_tripwires,
            "scan_for_new_hosts":  self._tool_scan_for_new_hosts,
            "alert_engineer":      self._tool_alert_engineer,
        }

    # ── Tool implementations ─────────────────────────────────────────────

    async def _tool_check_host_changes(self, args: dict) -> str:
        host  = args.get("host", "")
        ports = args.get("ports", "")   # optional: comma-separated port list to check

        if not host:
            return "ERROR: host is required"

        await self.cc.heartbeat(status="running", current_task=f"checking host {host}")

        import uuid as _uuid
        port_flag = f"-p {ports}" if ports else "--top-ports 1000"
        xml_file  = f"/tmp/nmap_{_uuid.uuid4().hex}.xml"
        # Normal output to stdout (terminal feed), XML to temp file (parsed silently)
        cmd = f"nmap -sV -T4 --open {port_flag} -oX {xml_file} -oN - {host}"

        result = await self.cc.execute(cmd, target=host, technique="T0000", timeout=120)
        if result.get("exit_code", -1) != 0 and not result.get("stdout", ""):
            err = result.get("stderr", "no output")
            return f"Scan failed for {host}: {err[:200]}"

        # Read XML silently (internal parse — not shown in terminal feed)
        xml_result    = await self.cc.execute(
            f"cat {xml_file} 2>/dev/null; rm -f {xml_file}",
            target=host, technique="T0000", timeout=10, silent=True,
        )
        xml_text      = xml_result.get("stdout", "")

        # Parse nmap XML output into port list
        current_ports = _parse_nmap_xml_ports(xml_text)

        # Run anomaly detection against baseline
        anomalies = await self._detector.check_host(host, current_ports)

        if not anomalies:
            return f"No changes detected on {host}. {len(current_ports)} ports open."

        # Record anomalies
        lines = [f"CHANGES DETECTED on {host}: {len(anomalies)} anomaly/anomalies"]
        for a in anomalies:
            lines.append(
                f"  [{a.severity.upper()}] {a.anomaly_type.value}: {a.description}"
            )
            await self.commander.write_anomaly(
                host=host,
                anomaly_type=a.anomaly_type.value,
                description=a.description,
                severity=a.severity,
            )

        return "\n".join(lines)

    async def _tool_deploy_tripwire(self, args: dict) -> str:
        host          = args.get("host", "")
        tripwire_type = args.get("tripwire_type", "honeytoken_file")
        extra_port    = int(args.get("port", 9999))
        extra_path    = args.get("path", "/tmp/.secunet_canary")

        if not host:
            return "ERROR: host is required"

        # Create the tripwire dataclass
        ttype = tripwire_type.lower()
        if ttype == "honeytoken_file":
            tripwire = create_honeytoken_file(host, path=extra_path)
        elif ttype == "fake_credential":
            tripwire = create_fake_credential(host)
        elif ttype == "canary_port_listener":
            tripwire = create_canary_listener(host, port=extra_port)
        elif ttype == "audit_rule":
            tripwire = create_audit_rule(host, path=extra_path)
        else:
            return f"ERROR: unknown tripwire_type '{tripwire_type}'"

        # Deploy it on the target host
        await self.cc.heartbeat(
            status="running",
            current_task=f"deploying {ttype} tripwire on {host}",
        )
        result = await self.cc.execute(
            command=tripwire.deploy_command,
            target=host,
            technique="T0000",
            timeout=60,
        )
        exit_code = result.get("exit_code", -1)
        stdout    = result.get("stdout", "").strip()
        stderr    = result.get("stderr", "").strip()

        if exit_code != 0:
            # Remove from in-memory store — deploy failed
            DEPLOYED.pop(tripwire.tripwire_id, None)
            return (
                f"DEPLOY FAILED for {ttype} tripwire on {host} "
                f"(exit {exit_code}): {stderr[:200]}"
            )

        # Write tripwire state to Commander
        await self.cc.write_event("tripwire_state", {
            "tripwire_id":  tripwire.tripwire_id,
            "host":         host,
            "tripwire_type": ttype,
            "description":  tripwire.description,
            "status":       "deployed",
            "alert_condition": tripwire.alert_condition,
        })

        return (
            f"Tripwire deployed: {ttype} on {host} "
            f"(id={tripwire.tripwire_id[:8]}). "
            f"Deploy output: {stdout[:100] or '(none)'}"
        )

    async def _tool_check_tripwires(self, args: dict) -> str:
        host = args.get("host", "")

        if host:
            tripwires = get_tripwires_for_host(host)
        else:
            tripwires = all_tripwires()

        if not tripwires:
            target_label = host or "all hosts"
            return f"No tripwires deployed on {target_label}"

        await self.cc.heartbeat(
            status="running",
            current_task=f"checking tripwires on {host or 'all hosts'}",
        )

        report_lines = []
        triggered_count = 0

        for tripwire in tripwires:
            result = await self.cc.execute(
                command=tripwire.check_command,
                target=tripwire.host,
                technique="T0000",
                timeout=30,
            )
            stdout    = result.get("stdout", "")
            exit_code = result.get("exit_code", -1)

            if exit_code != 0 or not stdout:
                report_lines.append(
                    f"[{tripwire.tripwire_id[:8]}] Check failed on {tripwire.host}: "
                    f"{result.get('stderr', 'no output')[:100]}"
                )
                continue

            anomaly = await self._detector.check_tripwire(stdout, tripwire)

            if anomaly:
                triggered_count += 1
                report_lines.append(
                    f"[TRIGGERED] {tripwire.tripwire_id[:8]} on {tripwire.host}: "
                    f"{anomaly.description[:120]}"
                )
                # Write anomaly event to Commander
                await self.commander.write_anomaly(
                    host=tripwire.host,
                    anomaly_type=anomaly.anomaly_type.value,
                    description=anomaly.description,
                    severity=anomaly.severity,
                )
                # Alert if critical
                if anomaly.severity in ("critical", "high"):
                    await self.cc.send_message(
                        f"TRIPWIRE ALERT on {tripwire.host}: {anomaly.description[:200]}",
                        msg_type="alert",
                    )
            else:
                report_lines.append(
                    f"[OK] {tripwire.tripwire_id[:8]} on {tripwire.host} "
                    f"({tripwire.tripwire_type.value})"
                )

        summary = (
            f"Tripwire check complete: {len(tripwires)} checked, "
            f"{triggered_count} triggered.\n" + "\n".join(report_lines)
        )
        return summary

    async def _tool_scan_for_new_hosts(self, args: dict) -> str:
        scope = args.get("scope") or await self.cc.get_target_scope()

        if not scope:
            return "ERROR: scope is required (set it from the dashboard)"

        await self.cc.heartbeat(status="running", current_task=f"ping sweep {scope}")

        import uuid as _uuid
        xml_file = f"/tmp/nmap_{_uuid.uuid4().hex}.xml"
        # Normal output to stdout (terminal feed), XML to temp file (parsed silently)
        cmd    = f"nmap -sn -T4 {scope} -oX {xml_file} -oN -"
        result = await self.cc.execute(cmd, target=scope, technique="T0000", timeout=120)

        if result.get("exit_code", -1) != 0 and not result.get("stdout", ""):
            return f"Ping sweep failed for {scope}: {result.get('stderr', '')[:200]}"

        # Read XML silently
        xml_result = await self.cc.execute(
            f"cat {xml_file} 2>/dev/null; rm -f {xml_file}",
            target=scope, technique="T0000", timeout=10, silent=True,
        )
        xml_text = xml_result.get("stdout", "")

        # Parse live hosts from XML
        live_hosts = _parse_nmap_xml_hosts(xml_text)

        if not live_hosts:
            return f"No live hosts found in scope {scope}"

        new_hosts = []
        for host in live_hosts:
            anomaly = await self._detector.check_new_host(host)
            if anomaly:
                new_hosts.append(host)
                await self.commander.write_anomaly(
                    host=host,
                    anomaly_type=anomaly.anomaly_type.value,
                    description=anomaly.description,
                    severity=anomaly.severity,
                )
                # Also write asset discovery
                await self.commander.write_asset_discovery(host=host)

        if not new_hosts:
            return (
                f"Ping sweep complete. {len(live_hosts)} hosts live in {scope}. "
                f"No new hosts detected."
            )

        # Notify @recon to perform full scan on new hosts
        for h in new_hosts:
            await self.cc.send_message(
                content=(
                    f"New host discovered: {h}. "
                    f"Please perform a full port scan and service fingerprint."
                ),
                to="recon-agent",
                msg_type="task",
            )
            # Establish baseline with empty port list (recon will fill it in)
            self._detector.update_baseline(h, [])

        return (
            f"Ping sweep complete. {len(live_hosts)} hosts live in {scope}. "
            f"NEW HOSTS: {', '.join(new_hosts)}. "
            f"Notified @recon for full scans."
        )

    async def _tool_alert_engineer(self, args: dict) -> str:
        message  = args.get("message", "")
        severity = args.get("severity", "high")

        if not message:
            return "ERROR: message is required"

        await self.cc.send_message(content=message, msg_type="alert")
        logger.warning("[monitor-agent] ALERT [%s]: %s", severity.upper(), message[:120])

        # For critical events, also submit a HITL so the engineer sees it immediately
        if severity.lower() == "critical":
            hitl_resp = await self.cc.request_hitl(
                action="Critical security event — review required",
                target="monitor-agent",
                risk_level="CRITICAL",
                context=message,
                proposed_command=None,
            )
            hitl_id = hitl_resp.get("hitl_id", "")
            if hitl_id:
                return (
                    f"CRITICAL alert sent and HITL raised (id={hitl_id[:8]}). "
                    f"Message: {message[:100]}"
                )

        return f"Alert sent [{severity.upper()}]: {message[:100]}"

    # ── Primary cycle ─────────────────────────────────────────────────────

    async def run_cycle(self) -> None:
        """Monitoring loop: runs indefinitely on MONITOR_INTERVAL."""
        while True:
            try:
                await self._do_monitor_cycle()
            except Exception:
                logger.exception("[monitor-agent] Cycle failed")
            logger.info("[monitor-agent] Cycle complete. Next check in %ds", MONITOR_INTERVAL)
            await asyncio.sleep(MONITOR_INTERVAL)

    async def _do_monitor_cycle(self) -> None:
        logger.info("[monitor-agent] Starting monitor cycle")
        await self.cc.heartbeat(status="running", current_task="monitor cycle")

        scope = await self.cc.get_target_scope()

        # 1. Get known hosts from Commander
        context = await self.commander.ask(
            "List all known hosts and their last-known open ports and services. "
            "Also list any recent patches deployed or anomalies detected."
        )

        known_hosts = self._detector.known_hosts()
        logger.info("[monitor-agent] Monitoring %d known hosts", len(known_hosts))

        # 2. Build LLM prompt for this cycle
        prompt = f"""MONITOR CYCLE — Current state:

KNOWN HOSTS (from local baseline): {', '.join(known_hosts) if known_hosts else 'none yet'}

COMMANDER CONTEXT:
{context}

TARGET SCOPE: {scope or '(not set)'}

Your tasks for this cycle:
1. For each known host, call check_host_changes to detect port/service changes.
2. Call check_tripwires to verify all deployed tripwires are intact.
3. If TARGET_SCOPE is set, call scan_for_new_hosts to find any new devices.
4. For any HIGH or CRITICAL anomalies, call alert_engineer.
5. If new hosts were found, also call deploy_tripwire on each new host (honeytoken_file).

Be efficient — work through all hosts systematically.
"""

        result = await self.think_and_act(prompt, max_tokens=4096)

        # 3. Broadcast summary
        await self.cc.send_message(
            f"Monitor cycle complete.\n\n{result[:500]}"
        )
        logger.info("[monitor-agent] Monitor cycle complete")

    # ── Inbox handler ─────────────────────────────────────────────────────

    async def _handle_inbox(self, message: dict) -> None:
        """
        Handle messages from other agents.
        @recon sends asset_discovery, @remediate sends patch notifications.
        """
        content = message.get("content", "")
        sender  = message.get("from_id", "unknown")

        if not content:
            return

        logger.info("[monitor-agent] Inbox from %s: %s", sender, content[:80])

        # If recon discovered a new host, establish baseline and deploy tripwires
        if "recon" in sender.lower() and (
            "discovered" in content.lower() or "new host" in content.lower()
        ):
            context = await self.commander.ask(
                f"What ports and services are known for the host mentioned here: {content}"
            )
            prompt = (
                f"MESSAGE FROM {sender.upper()} (New Asset Notification):\n{content}\n\n"
                f"CONTEXT:\n{context}\n\n"
                "Extract the new host IP. Deploy a honeytoken_file tripwire on it. "
                "Update the baseline. Notify @exploit about the new attack surface."
            )
        elif "remediate" in sender.lower():
            context = await self.commander.ask(
                f"What was patched and what is the current state of detection? {content}"
            )
            prompt = (
                f"MESSAGE FROM {sender.upper()} (Patch Notification):\n{content}\n\n"
                f"CONTEXT:\n{context}\n\n"
                "Acknowledge the patch. Check if any tripwires need updating. "
                "If the patch changed service versions, update the baseline accordingly."
            )
        else:
            context = await self.commander.ask(content)
            prompt = f"MESSAGE FROM {sender.upper()}: {content}\n\nCONTEXT:\n{context}"

        try:
            reply = await self.think_and_act(prompt, max_tokens=4096)
        except Exception as exc:
            reply = f"[monitor-agent] Error processing message: {exc}"

        await self.cc.send_message(reply, to=sender)


# ── nmap XML parsing helpers ──────────────────────────────────────────────────

def _parse_nmap_xml_ports(xml: str) -> list[dict]:
    """
    Lightweight nmap XML parser. Returns a list of port dicts:
      {"port": int, "protocol": str, "state": str, "service": str, "version": str}
    Falls back to an empty list on any parse error.
    """
    if not xml or "<nmaprun" not in xml:
        return []

    try:
        import xml.etree.ElementTree as ET
        root    = ET.fromstring(xml)
        ports   = []
        for host_el in root.findall("host"):
            for port_el in host_el.findall(".//port"):
                state_el   = port_el.find("state")
                service_el = port_el.find("service")
                state   = state_el.get("state", "closed") if state_el is not None else "closed"
                service = ""
                version = ""
                if service_el is not None:
                    service = service_el.get("name", "")
                    version = service_el.get("version", "")
                    product = service_el.get("product", "")
                    if product and not version:
                        version = product
                ports.append({
                    "port":     int(port_el.get("portid", 0)),
                    "protocol": port_el.get("protocol", "tcp"),
                    "state":    state,
                    "service":  service,
                    "version":  version,
                })
        return ports
    except Exception as exc:
        logger.debug("[monitor-agent] nmap XML port parse error: %s", exc)
        return []


def _parse_nmap_xml_hosts(xml: str) -> list[str]:
    """
    Parse nmap XML ping sweep output. Returns list of live host IP strings.
    """
    if not xml or "<nmaprun" not in xml:
        return []

    try:
        import xml.etree.ElementTree as ET
        root  = ET.fromstring(xml)
        hosts = []
        for host_el in root.findall("host"):
            state_el = host_el.find("status")
            if state_el is not None and state_el.get("state") != "up":
                continue
            for addr_el in host_el.findall("address"):
                if addr_el.get("addrtype") == "ipv4":
                    hosts.append(addr_el.get("addr", ""))
        return [h for h in hosts if h]
    except Exception as exc:
        logger.debug("[monitor-agent] nmap XML host parse error: %s", exc)
        return []
