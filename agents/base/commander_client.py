"""
Commander client — convenience wrappers used by every agent.
Sits on top of CCClient to provide typed, domain-specific writes.
"""
import uuid
import logging
from datetime import datetime, timezone

from cc_client import CCClient

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CommanderClient:
    def __init__(self, cc: CCClient):
        self._cc = cc

    async def ask(self, question: str) -> str:
        """Ask Commander for context about this question."""
        return await self._cc.query_commander(question)

    async def write_scan_result(self, host: str, ports: list, os_guess: str = "", raw: str = "") -> None:
        await self._cc.write_event("scan_result", {
            "host": host, "ports": ports, "os_guess": os_guess, "raw": raw[:500],
        })

    async def write_service_fingerprint(self, host: str, port: int, protocol: str,
                                         service: str, version: str, banner: str = "") -> None:
        await self._cc.write_event("service_fingerprint", {
            "host": host, "port": port, "protocol": protocol,
            "service": service, "version": version, "banner": banner[:200],
        })

    async def write_asset_discovery(self, host: str, hostnames: list = None,
                                     mac: str = "", os_guess: str = "") -> None:
        await self._cc.write_event("asset_discovery", {
            "host": host, "hostnames": hostnames or [], "mac": mac, "os_guess": os_guess,
        })

    async def write_vulnerability(self, host: str, port: int, service: str,
                                   cve: str, cvss: float, severity: str,
                                   title: str, description: str, technique: str = "") -> str:
        finding_id = str(uuid.uuid4())
        await self._cc.write_event("vulnerability_finding", {
            "finding_id": finding_id, "host": host, "port": port,
            "service": service, "cve": cve, "cvss": cvss,
            "severity": severity, "title": title, "description": description, "technique": technique,
        })
        return finding_id

    async def write_exploit_attempt(self, host: str, port: int, module: str,
                                     cve: str, outcome: str, output: str = "",
                                     access_level: str = "") -> None:
        await self._cc.write_event("exploit_attempt", {
            "host": host, "port": port, "module": module, "cve": cve,
            "outcome": outcome, "output": output[:500], "access_level": access_level,
        })

    async def write_detection_score(self, technique: str, score: float,
                                     alert_triggered: bool, siem: str = "",
                                     rule_matched: str = "") -> None:
        await self._cc.write_event("detection_score", {
            "technique": technique, "score": score,
            "alert_triggered": alert_triggered, "siem": siem, "rule_matched": rule_matched,
        })

    async def write_patch_deployed(self, host: str, cve: str, action: str,
                                    success: bool, output: str = "") -> None:
        await self._cc.write_event("patch_deployed", {
            "host": host, "cve": cve, "action": action, "success": success, "output": output[:300],
        })

    async def write_anomaly(self, host: str, anomaly_type: str,
                             description: str, severity: str = "medium") -> None:
        await self._cc.write_event("anomaly_event", {
            "host": host, "anomaly_type": anomaly_type,
            "description": description, "severity": severity,
        })
