"""
CVE lookup via NIST NVD API v2.
No API key required for basic queries (rate-limited to 5 req/30s without key).
Set NVD_API_KEY env var to get 50 req/30s.
"""
import os
import asyncio
import logging
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

NVD_BASE      = "https://services.nvd.nist.gov/rest/json/cves/2.0"
NVD_API_KEY   = os.getenv("NVD_API_KEY", "")
REQUEST_DELAY = 0.6 if NVD_API_KEY else 6.0  # rate limit compliance


def _headers() -> dict:
    h = {"User-Agent": "SecuNet-Agent/1.0"}
    if NVD_API_KEY:
        h["apiKey"] = NVD_API_KEY
    return h


def _cvss_to_severity(score: float) -> str:
    if score >= 9.0:  return "critical"
    if score >= 7.0:  return "high"
    if score >= 4.0:  return "medium"
    if score > 0:     return "low"
    return "info"


def _parse_cve(item: dict) -> dict | None:
    """Extract fields from a single NVD CVE item."""
    try:
        cve_id = item["cve"]["id"]
        desc   = next(
            (d["value"] for d in item["cve"].get("descriptions", []) if d["lang"] == "en"),
            "No description available."
        )

        # CVSS score — try v3.1, v3.0, v2 in that order
        cvss   = 0.0
        vector = ""
        metrics = item["cve"].get("metrics", {})
        for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
            entries = metrics.get(key, [])
            if entries:
                data = entries[0].get("cvssData", {})
                cvss   = float(data.get("baseScore", 0))
                vector = data.get("vectorString", "")
                break

        severity = _cvss_to_severity(cvss)

        # References
        refs = [r["url"] for r in item["cve"].get("references", [])[:3]]

        # Published date
        published = item["cve"].get("published", "")[:10]

        return {
            "cve":         cve_id,
            "cvss":        cvss,
            "severity":    severity,
            "description": desc[:400],
            "vector":      vector,
            "references":  refs,
            "published":   published,
        }
    except (KeyError, TypeError, ValueError) as exc:
        logger.debug("CVE parse error: %s", exc)
        return None


async def lookup_cve(cve_id: str) -> dict | None:
    """Look up a single CVE by ID. Returns structured dict or None."""
    url = NVD_BASE
    params = {"cveId": cve_id}
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            r = await client.get(url, params=params, headers=_headers())
            r.raise_for_status()
            data = r.json()
            vulns = data.get("vulnerabilities", [])
            if vulns:
                return _parse_cve(vulns[0])
        except Exception as exc:
            logger.error("CVE lookup failed for %s: %s", cve_id, exc)
    return None


async def search_by_keyword(keyword: str, limit: int = 10) -> list[dict]:
    """
    Search NVD for CVEs matching a keyword (e.g. "Apache 2.4.49").
    Returns up to `limit` results sorted by CVSS score descending.
    """
    params: dict = {
        "keywordSearch": keyword,
        "resultsPerPage": min(limit, 20),
    }
    async with httpx.AsyncClient(timeout=20) as client:
        try:
            await asyncio.sleep(REQUEST_DELAY)
            r = await client.get(NVD_BASE, params=params, headers=_headers())
            r.raise_for_status()
            data = r.json()
            results = []
            for item in data.get("vulnerabilities", []):
                parsed = _parse_cve(item)
                if parsed:
                    results.append(parsed)
            results.sort(key=lambda x: x["cvss"], reverse=True)
            return results[:limit]
        except Exception as exc:
            logger.error("CVE keyword search failed (%r): %s", keyword, exc)
            return []


async def lookup_service_cves(service: str, version: str, limit: int = 5) -> list[dict]:
    """
    Find CVEs for a specific service + version string.
    e.g. service="OpenSSH", version="8.2"
    """
    query = f"{service} {version}".strip()
    if not query:
        return []
    return await search_by_keyword(query, limit=limit)
