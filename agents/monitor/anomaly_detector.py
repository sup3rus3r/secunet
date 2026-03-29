# FILE: agents/monitor/anomaly_detector.py
"""
Anomaly detector — threshold-based detection of suspicious activity.
Monitors scan results, connection logs, and resource usage for deviations.
"""
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


# ── Enums and dataclasses ────────────────────────────────────────────────────

class AnomalyType(Enum):
    NEW_OPEN_PORT       = "new_open_port"
    SERVICE_CHANGE      = "service_change"
    NEW_HOST            = "new_host"
    UNUSUAL_TRAFFIC     = "unusual_traffic"
    TRIPWIRE_TRIGGERED  = "tripwire_triggered"
    HIGH_RESOURCE_USAGE = "high_resource_usage"


@dataclass
class Anomaly:
    anomaly_id:   str
    anomaly_type: AnomalyType
    host:         str
    description:  str
    severity:     str
    evidence:     str
    detected_at:  str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ── Helpers ──────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _severity_for_anomaly(anomaly_type: AnomalyType) -> str:
    severity_map = {
        AnomalyType.NEW_OPEN_PORT:       "medium",
        AnomalyType.SERVICE_CHANGE:      "medium",
        AnomalyType.NEW_HOST:            "high",
        AnomalyType.UNUSUAL_TRAFFIC:     "high",
        AnomalyType.TRIPWIRE_TRIGGERED:  "critical",
        AnomalyType.HIGH_RESOURCE_USAGE: "low",
    }
    return severity_map.get(anomaly_type, "medium")


# ── AnomalyDetector ──────────────────────────────────────────────────────────

class AnomalyDetector:
    """
    Stateful anomaly detector that tracks known host/port/service baselines
    and flags deviations as Anomaly objects.
    """

    def __init__(self):
        # host -> {"ports": {port_num: {"service": str, "version": str, "protocol": str}},
        #          "last_seen": str}
        self._known_hosts: dict[str, dict] = {}

    # ── Public API ───────────────────────────────────────────────────────

    async def check_host(self, host: str, current_ports: list[dict]) -> list[Anomaly]:
        """
        Compare current_ports against the known baseline for host.
        Returns a list of Anomaly objects for any deviations found.

        Each port dict should contain at minimum:
          {"port": int, "service": str, "version": str, "protocol": str, "state": str}
        """
        anomalies: list[Anomaly] = []

        if host not in self._known_hosts:
            # First time seeing this host — establish baseline, no anomalies yet.
            # check_new_host() should be called separately for NEW_HOST detection.
            self.update_baseline(host, current_ports)
            return anomalies

        known = self._known_hosts[host]
        known_ports: dict[int, dict] = known.get("ports", {})

        # Build a map of current open ports
        current_open: dict[int, dict] = {}
        for p in current_ports:
            if p.get("state", "open") == "open":
                current_open[int(p["port"])] = p

        # Check for new ports
        for port_num, pdata in current_open.items():
            if port_num not in known_ports:
                service  = pdata.get("service", "unknown")
                version  = pdata.get("version", "")
                protocol = pdata.get("protocol", "tcp")
                anomaly = Anomaly(
                    anomaly_id=str(uuid.uuid4()),
                    anomaly_type=AnomalyType.NEW_OPEN_PORT,
                    host=host,
                    description=(
                        f"New open port detected: {protocol}/{port_num} "
                        f"({service} {version}). This port was not in the baseline."
                    ),
                    severity=_severity_for_anomaly(AnomalyType.NEW_OPEN_PORT),
                    evidence=(
                        f"port={port_num} protocol={protocol} "
                        f"service={service} version={version}"
                    ),
                )
                anomalies.append(anomaly)
                logger.info("[anomaly_detector] NEW_OPEN_PORT on %s: %s/%d (%s %s)",
                            host, protocol, port_num, service, version)

        # Check for service/version changes on existing ports
        for port_num, known_pdata in known_ports.items():
            if port_num not in current_open:
                # Port closed — log at debug, not an anomaly by default
                logger.debug("[anomaly_detector] Port %d closed on %s (was %s)",
                             port_num, host, known_pdata.get("service", "?"))
                continue

            curr_pdata    = current_open[port_num]
            known_service = known_pdata.get("service", "")
            curr_service  = curr_pdata.get("service", "")
            known_version = known_pdata.get("version", "")
            curr_version  = curr_pdata.get("version", "")

            service_changed = (
                known_service and curr_service
                and known_service.lower() != curr_service.lower()
            )
            version_changed = (
                known_version and curr_version and known_version != curr_version
            )

            if service_changed or version_changed:
                protocol = curr_pdata.get("protocol", known_pdata.get("protocol", "tcp"))
                description = f"Service change on {host}:{port_num} ({protocol}). "
                evidence_parts = []
                if service_changed:
                    description += f"Service: {known_service!r} -> {curr_service!r}. "
                    evidence_parts.append(f"service: {known_service!r} -> {curr_service!r}")
                if version_changed:
                    description += f"Version: {known_version!r} -> {curr_version!r}."
                    evidence_parts.append(f"version: {known_version!r} -> {curr_version!r}")

                anomaly = Anomaly(
                    anomaly_id=str(uuid.uuid4()),
                    anomaly_type=AnomalyType.SERVICE_CHANGE,
                    host=host,
                    description=description.strip(),
                    severity=_severity_for_anomaly(AnomalyType.SERVICE_CHANGE),
                    evidence=f"port={port_num} " + " | ".join(evidence_parts),
                )
                anomalies.append(anomaly)
                logger.info("[anomaly_detector] SERVICE_CHANGE on %s port %d: %s",
                            host, port_num, " | ".join(evidence_parts))

        return anomalies

    async def check_new_host(self, host: str) -> Optional[Anomaly]:
        """
        Returns a NEW_HOST Anomaly if this host has not been seen before.
        Does NOT update the baseline — call update_baseline() after investigating.
        """
        if host not in self._known_hosts:
            logger.info("[anomaly_detector] NEW_HOST detected: %s", host)
            return Anomaly(
                anomaly_id=str(uuid.uuid4()),
                anomaly_type=AnomalyType.NEW_HOST,
                host=host,
                description=(
                    f"Previously unknown host {host} discovered in scope. "
                    "This may indicate a new device, rogue system, or VM spun up."
                ),
                severity=_severity_for_anomaly(AnomalyType.NEW_HOST),
                evidence=f"host={host} first_seen={_now()}",
            )
        return None

    async def check_tripwire(
        self,
        tripwire_output: str,
        tripwire: object,
    ) -> Optional[Anomaly]:
        """
        Parse the output of a tripwire check command to detect activation.

        tripwire: a Tripwire dataclass instance from tripwire_deployer.
        tripwire_output: stdout from the tripwire's check_command.

        Returns a TRIPWIRE_TRIGGERED Anomaly if the tripwire was activated, else None.
        """
        if not tripwire_output:
            return None

        tripwire_id = getattr(tripwire, "tripwire_id", "unknown")
        host        = getattr(tripwire, "host", "unknown")
        ttype       = getattr(tripwire, "tripwire_type", None)
        description = getattr(tripwire, "description", "")
        metadata    = getattr(tripwire, "metadata", {})
        alert_cond  = getattr(tripwire, "alert_condition", "")

        triggered = False
        evidence  = ""

        if ttype is not None:
            ttype_val = ttype.value if hasattr(ttype, "value") else str(ttype)

            if "honeytoken_file" in ttype_val:
                # Check if mtime changed from baseline
                baseline_mtime = metadata.get("baseline_mtime")
                try:
                    lines = [ln.strip() for ln in tripwire_output.splitlines() if ln.strip()]
                    mtime_lines = [ln for ln in lines if ln.isdigit()]
                    if mtime_lines:
                        current_mtime = int(mtime_lines[-1])
                        if baseline_mtime is None:
                            metadata["baseline_mtime"] = current_mtime
                        elif current_mtime != baseline_mtime:
                            triggered = True
                            evidence = (
                                f"File mtime changed: baseline={baseline_mtime} "
                                f"current={current_mtime}"
                            )
                except (ValueError, IndexError):
                    pass

            elif "fake_credential" in ttype_val:
                # Check if atime changed or auth log count increased
                baseline_atime      = metadata.get("baseline_atime")
                baseline_auth_count = metadata.get("baseline_auth_count", 0)
                lines = [ln.strip() for ln in tripwire_output.splitlines() if ln.strip()]
                try:
                    if len(lines) >= 1 and lines[0].isdigit():
                        current_atime = int(lines[0])
                        if baseline_atime is None:
                            metadata["baseline_atime"] = current_atime
                        elif current_atime != baseline_atime:
                            triggered = True
                            evidence = (
                                f"Credential file atime changed: "
                                f"baseline={baseline_atime} current={current_atime}"
                            )
                    if len(lines) >= 2 and lines[1].isdigit():
                        current_auth = int(lines[1])
                        if current_auth > baseline_auth_count:
                            triggered = True
                            evidence += (
                                f" | Auth log hits for fake username: "
                                f"{baseline_auth_count} -> {current_auth}"
                            )
                        metadata["baseline_auth_count"] = current_auth
                except (ValueError, IndexError):
                    pass

            elif "canary_port_listener" in ttype_val:
                baseline_size = metadata.get("baseline_size", 0)
                current_size  = len(tripwire_output.strip())
                if current_size > baseline_size:
                    triggered = True
                    evidence = (
                        f"Canary port {metadata.get('port', '?')} received connection. "
                        f"Log size: {baseline_size} -> {current_size} bytes. "
                        f"Data: {tripwire_output[:200]}"
                    )
                metadata["baseline_size"] = current_size

            elif "audit_rule" in ttype_val:
                stripped = tripwire_output.strip()
                if stripped and "<no matches>" not in stripped.lower():
                    if "no records found" not in stripped.lower():
                        triggered = True
                        evidence = (
                            f"Audit rule fired for {metadata.get('path', '?')}:\n"
                            f"{stripped[:300]}"
                        )

        if not triggered:
            return None

        logger.warning("[anomaly_detector] TRIPWIRE_TRIGGERED: %s on %s — %s",
                       tripwire_id[:8], host, evidence[:80])

        return Anomaly(
            anomaly_id=str(uuid.uuid4()),
            anomaly_type=AnomalyType.TRIPWIRE_TRIGGERED,
            host=host,
            description=(
                f"Tripwire activated on {host}. "
                f"Tripwire: {description[:150]}. "
                f"Alert condition: {alert_cond}"
            ),
            severity=_severity_for_anomaly(AnomalyType.TRIPWIRE_TRIGGERED),
            evidence=evidence,
        )

    def update_baseline(self, host: str, ports: list[dict]) -> None:
        """
        Update the known-good state for a host.
        Call this after anomalies have been investigated and confirmed benign,
        or when establishing the initial baseline for a newly discovered host.
        """
        port_map: dict[int, dict] = {}
        for p in ports:
            if p.get("state", "open") == "open":
                port_num = int(p["port"])
                port_map[port_num] = {
                    "service":  p.get("service", ""),
                    "version":  p.get("version", ""),
                    "protocol": p.get("protocol", "tcp"),
                }

        self._known_hosts[host] = {
            "ports":     port_map,
            "last_seen": _now(),
        }
        logger.debug("[anomaly_detector] Baseline updated for %s: %d ports", host, len(port_map))

    def known_hosts(self) -> list[str]:
        """Return a list of all hosts with established baselines."""
        return list(self._known_hosts.keys())

    def host_baseline(self, host: str) -> Optional[dict]:
        """Return the baseline dict for a host, or None if unknown."""
        return self._known_hosts.get(host)
