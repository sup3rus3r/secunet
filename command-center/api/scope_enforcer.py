"""
Scope enforcer.
Validates that every execution target falls within the
authorised TARGET_SCOPE CIDR. Hard gate — no exceptions.
"""
import ipaddress
import os
import logging
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

_scope: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []


def load_scope() -> None:
    """Parse TARGET_SCOPE env var. Called once at startup."""
    raw = os.getenv("TARGET_SCOPE", "")
    if not raw:
        logger.warning("TARGET_SCOPE not set — all targets will be BLOCKED")
        return
    for cidr in [s.strip() for s in raw.split(",") if s.strip()]:
        try:
            _scope.append(ipaddress.ip_network(cidr, strict=False))
            logger.info("Scope loaded: %s", cidr)
        except ValueError:
            logger.error("Invalid CIDR in TARGET_SCOPE: %s", cidr)


def is_allowed(target: str) -> bool:
    """Return True if target IP/CIDR is within authorised scope."""
    if not _scope:
        return False
    try:
        # Try as a single address first
        addr = ipaddress.ip_address(target)
        return any(addr in net for net in _scope)
    except ValueError:
        pass
    try:
        # Try as a network — allowed if it's a subnet of any scope network
        net = ipaddress.ip_network(target, strict=False)
        return any(net.subnet_of(s) or net == s for s in _scope)
    except ValueError:
        # target may be a hostname — resolve not supported, block it
        return False


def enforce(target: str) -> None:
    """
    Raise HTTP 403 if target is out of scope.
    Use as a guard at the top of any execution handler.
    """
    if not is_allowed(target):
        logger.warning("SCOPE VIOLATION: %s is outside authorised scope", target)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Target {target!r} is outside authorised scope. Request blocked.",
        )


def set_scope(cidrs: list[str]) -> None:
    """Replace the live scope list at runtime (called by /mission/scope API)."""
    global _scope
    _scope.clear()
    for cidr in [c.strip() for c in cidrs if c.strip()]:
        try:
            _scope.append(ipaddress.ip_network(cidr, strict=False))
            logger.info("Scope updated: %s", cidr)
        except ValueError:
            logger.error("Invalid CIDR: %s", cidr)


def get_scope_strings() -> list[str]:
    return [str(net) for net in _scope]
