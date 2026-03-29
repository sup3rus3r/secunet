# FILE: agents/detect/siem/splunk.py
"""
Splunk REST API client.
Queries Splunk for evidence of a technique being detected.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

SPLUNK_POLL_INTERVAL = 2   # seconds between job-status polls
SPLUNK_POLL_TIMEOUT  = 60  # max seconds to wait for a search job


class SplunkClient:
    def __init__(self) -> None:
        self._url   = os.getenv("SPLUNK_URL", "").rstrip("/")
        self._token = os.getenv("SPLUNK_TOKEN", "")
        self._http: httpx.AsyncClient | None = None

    # ── Lazy HTTP client ──────────────────────────────────────────────────

    def _client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                base_url=self._url,
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "Content-Type":  "application/x-www-form-urlencoded",
                },
                verify=False,  # Common for internal Splunk deployments
                timeout=30,
            )
        return self._http

    # ── Availability ──────────────────────────────────────────────────────

    @property
    def available(self) -> bool:
        """True if SPLUNK_URL and SPLUNK_TOKEN are configured."""
        return bool(self._url and self._token)

    # ── Core search ───────────────────────────────────────────────────────

    async def search(self, query: str, earliest: str = "-1h") -> list[dict]:
        """
        Execute a Splunk SPL search and return the result rows as a list of dicts.

        Steps:
        1. POST /services/search/jobs  → get sid
        2. Poll GET /services/search/jobs/{sid} until dispatchState == DONE
        3. GET /services/search/jobs/{sid}/results?output_mode=json
        """
        if not self.available:
            logger.debug("[splunk] Client not configured — skipping search")
            return []

        client = self._client()

        # 1. Create the search job
        try:
            resp = await client.post(
                "/services/search/jobs",
                data={
                    "search":           f"search {query}",
                    "earliest_time":    earliest,
                    "latest_time":      "now",
                    "output_mode":      "json",
                    "exec_mode":        "normal",
                },
            )
            resp.raise_for_status()
            sid = resp.json().get("sid", "")
            if not sid:
                logger.error("[splunk] No SID in search response")
                return []
        except Exception as exc:
            logger.error("[splunk] Failed to create search job: %s", exc)
            return []

        # 2. Poll until done
        deadline = asyncio.get_event_loop().time() + SPLUNK_POLL_TIMEOUT
        while asyncio.get_event_loop().time() < deadline:
            await asyncio.sleep(SPLUNK_POLL_INTERVAL)
            try:
                status_resp = await client.get(
                    f"/services/search/jobs/{sid}",
                    params={"output_mode": "json"},
                )
                status_resp.raise_for_status()
                state = (
                    status_resp.json()
                    .get("entry", [{}])[0]
                    .get("content", {})
                    .get("dispatchState", "")
                )
                if state == "DONE":
                    break
                if state in ("FAILED", "CANCELED"):
                    logger.error("[splunk] Search job %s in state %s", sid, state)
                    return []
            except Exception as exc:
                logger.error("[splunk] Error polling job %s: %s", sid, exc)
                return []
        else:
            logger.warning("[splunk] Search job %s timed out", sid)
            return []

        # 3. Fetch results
        try:
            results_resp = await client.get(
                f"/services/search/jobs/{sid}/results",
                params={"output_mode": "json", "count": "100"},
            )
            results_resp.raise_for_status()
            rows: list[dict] = results_resp.json().get("results", [])
            return rows
        except Exception as exc:
            logger.error("[splunk] Failed to fetch results for job %s: %s", sid, exc)
            return []

    # ── Technique detection check ──────────────────────────────────────────

    async def check_technique(
        self,
        technique_id: str,
        host: str | None = None,
    ) -> dict[str, Any]:
        """
        Query Splunk for evidence that a MITRE ATT&CK technique was detected.

        Returns:
            {
                "detected":    bool,
                "alert_count": int,
                "events":      list[dict],
                "query_used":  str,
            }
        """
        host_filter = f' (src_ip="{host}" OR dest_ip="{host}" OR host="{host}")' if host else ""
        query = (
            f'index=* sourcetype=* '
            f'("{technique_id}" OR mitre_technique_id="{technique_id}" '
            f'OR threat.technique.id="{technique_id}"){host_filter} '
            f'| head 50'
        )

        try:
            events = await self.search(query, earliest="-1h")
        except Exception as exc:
            logger.error("[splunk] check_technique error: %s", exc)
            events = []

        return {
            "detected":    len(events) > 0,
            "alert_count": len(events),
            "events":      events[:20],
            "query_used":  query,
        }

    async def aclose(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()
