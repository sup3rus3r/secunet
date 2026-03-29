# FILE: agents/monitor/tripwire_deployer.py
"""
Tripwire deployer — places honeytokens and network sensors on discovered assets.
Tripwires are lightweight — they monitor for access/changes and alert.
"""
import uuid
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


# ── Enums and dataclasses ────────────────────────────────────────────────────

class TripwireType(Enum):
    HONEYTOKEN_FILE    = "honeytoken_file"
    FAKE_CREDENTIAL    = "fake_credential"
    CANARY_PORT_LISTENER = "canary_port_listener"
    AUDIT_RULE         = "audit_rule"


@dataclass
class Tripwire:
    tripwire_id:     str
    host:            str
    tripwire_type:   TripwireType
    description:     str
    deploy_command:  str
    check_command:   str
    alert_condition: str
    metadata:        dict = field(default_factory=dict)


# ── In-memory store ──────────────────────────────────────────────────────────

# Keyed by tripwire_id
DEPLOYED: dict[str, Tripwire] = {}


# ── Factory functions ────────────────────────────────────────────────────────

def create_honeytoken_file(
    host: str,
    path: str = "/tmp/.secunet_canary",
) -> Tripwire:
    """
    Place a canary file on the target host.
    If any process reads or modifies the file, the tripwire fires.
    """
    tripwire_id = str(uuid.uuid4())
    deploy_cmd = (
        f"echo \"SECUNET_CANARY_$(date +%s)\" > {path} && chmod 644 {path}"
    )
    check_cmd = (
        f"ls -la {path} && stat -c \"%Y\" {path}"
    )
    tripwire = Tripwire(
        tripwire_id=tripwire_id,
        host=host,
        tripwire_type=TripwireType.HONEYTOKEN_FILE,
        description=f"Canary file at {path} on {host}. Alerts if accessed or modified.",
        deploy_command=deploy_cmd,
        check_command=check_cmd,
        alert_condition=(
            "Alert if modification time (mtime) changes relative to baseline, "
            "or if the file is accessed (atime changes)."
        ),
        metadata={"path": path, "baseline_mtime": None},
    )
    DEPLOYED[tripwire_id] = tripwire
    logger.info("[tripwire_deployer] Created honeytoken_file tripwire %s on %s at %s",
                tripwire_id[:8], host, path)
    return tripwire


def create_fake_credential(host: str) -> Tripwire:
    """
    Deploy a fake credential entry in /tmp.
    The credential references a non-existent service; if it is used
    (e.g., an attacker tries to authenticate with it), the attempt will be
    logged in auth logs and the Commander anomaly detector can catch it.
    """
    tripwire_id = str(uuid.uuid4())
    cred_path   = f"/tmp/.secunet_creds_{tripwire_id[:8]}"
    # Fake entry format: service://user:password@host
    # The password contains the tripwire_id so we can correlate it in logs
    fake_cred   = f"ssh://secunet_monitor:{tripwire_id}@internal-vault.local"
    deploy_cmd  = (
        f"echo '{fake_cred}' > {cred_path} && chmod 600 {cred_path}"
    )
    check_cmd   = (
        # Check if the credential file was read (atime change) or if
        # the fake username has appeared in auth logs
        f"stat -c '%X' {cred_path} ; "
        f"grep -c 'secunet_monitor' /var/log/auth.log 2>/dev/null || echo 0"
    )
    tripwire = Tripwire(
        tripwire_id=tripwire_id,
        host=host,
        tripwire_type=TripwireType.FAKE_CREDENTIAL,
        description=(
            f"Fake credential file at {cred_path} on {host}. "
            "Alerts if the file is read or if authentication is attempted "
            "using the fake username 'secunet_monitor'."
        ),
        deploy_command=deploy_cmd,
        check_command=check_cmd,
        alert_condition=(
            "Alert if atime of credential file changes, or if "
            "'secunet_monitor' appears in /var/log/auth.log."
        ),
        metadata={
            "cred_path": cred_path,
            "fake_username": "secunet_monitor",
            "baseline_atime": None,
            "baseline_auth_count": 0,
        },
    )
    DEPLOYED[tripwire_id] = tripwire
    logger.info("[tripwire_deployer] Created fake_credential tripwire %s on %s",
                tripwire_id[:8], host)
    return tripwire


def create_canary_listener(host: str, port: int = 9999) -> Tripwire:
    """
    Deploy a netcat listener on an unused port.
    Any connection to the port indicates suspicious lateral movement or scanning.
    """
    tripwire_id = str(uuid.uuid4())
    log_file    = f"/tmp/.canary_{port}.log"
    deploy_cmd  = (
        f"nohup nc -lk {port} > {log_file} 2>&1 &"
    )
    check_cmd   = f"cat {log_file}"
    tripwire = Tripwire(
        tripwire_id=tripwire_id,
        host=host,
        tripwire_type=TripwireType.CANARY_PORT_LISTENER,
        description=(
            f"Canary port listener on {host}:{port}. "
            f"Logs all incoming connections to {log_file}."
        ),
        deploy_command=deploy_cmd,
        check_command=check_cmd,
        alert_condition=(
            f"Alert if {log_file} is non-empty (any connection to port {port} occurred)."
        ),
        metadata={"port": port, "log_file": log_file, "baseline_size": 0},
    )
    DEPLOYED[tripwire_id] = tripwire
    logger.info("[tripwire_deployer] Created canary_listener tripwire %s on %s:%d",
                tripwire_id[:8], host, port)
    return tripwire


def create_audit_rule(host: str, path: str) -> Tripwire:
    """
    Install a Linux audit rule to watch a filesystem path for read/write/exec/attribute changes.
    The auditd subsystem will log any access to the path.
    """
    tripwire_id = str(uuid.uuid4())
    deploy_cmd  = (
        f"auditctl -w {path} -p rwxa -k secunet_tripwire"
    )
    check_cmd   = (
        f"ausearch -k secunet_tripwire -ts recent 2>/dev/null || "
        f"auditctl -l | grep secunet_tripwire"
    )
    tripwire = Tripwire(
        tripwire_id=tripwire_id,
        host=host,
        tripwire_type=TripwireType.AUDIT_RULE,
        description=(
            f"Audit rule watching {path} on {host} for rwxa access. "
            "Uses Linux auditd; events are tagged with key 'secunet_tripwire'."
        ),
        deploy_command=deploy_cmd,
        check_command=check_cmd,
        alert_condition=(
            f"Alert if 'ausearch -k secunet_tripwire' returns any events for {path}."
        ),
        metadata={"path": path, "audit_key": "secunet_tripwire"},
    )
    DEPLOYED[tripwire_id] = tripwire
    logger.info("[tripwire_deployer] Created audit_rule tripwire %s on %s for path %s",
                tripwire_id[:8], host, path)
    return tripwire


# ── Convenience helpers ──────────────────────────────────────────────────────

def get_tripwires_for_host(host: str) -> list[Tripwire]:
    """Return all deployed tripwires for a given host."""
    return [t for t in DEPLOYED.values() if t.host == host]


def remove_tripwire(tripwire_id: str) -> Optional[Tripwire]:
    """Remove a tripwire from the in-memory store and return it."""
    return DEPLOYED.pop(tripwire_id, None)


def all_tripwires() -> list[Tripwire]:
    """Return all deployed tripwires."""
    return list(DEPLOYED.values())
