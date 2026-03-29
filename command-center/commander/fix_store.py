"""
Fix package store — holds per-finding ZIP artifacts in memory.

Keyed by finding_id. Agents POST their generated ZIP; the dashboard
GETs it for download. No persistence — packages are regenerated on
restart if needed.
"""
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# finding_id -> {bytes, filename, uploaded_at}
_packages: dict[str, dict] = {}


def store(finding_id: str, zip_bytes: bytes, host: str = "", cve: str = "") -> None:
    slug = f"fix-{host}-{cve}".lower().replace(" ", "-").replace(":", "-") if host or cve else finding_id
    _packages[finding_id] = {
        "bytes":       zip_bytes,
        "filename":    f"{slug}.zip",
        "size":        len(zip_bytes),
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }
    logger.info("Fix package stored for finding %s (%d bytes)", finding_id, len(zip_bytes))


def get(finding_id: str) -> dict | None:
    return _packages.get(finding_id)


def has(finding_id: str) -> bool:
    return finding_id in _packages


def list_all() -> list[dict]:
    return [
        {"finding_id": fid, "filename": v["filename"], "size": v["size"], "uploaded_at": v["uploaded_at"]}
        for fid, v in _packages.items()
    ]
