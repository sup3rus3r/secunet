# FILE: agents/detect/siem/sentinel.py
"""
Microsoft Sentinel client via Azure Monitor / Log Analytics REST API.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Log Analytics query endpoint
_LA_QUERY_URL = (
    "https://api.loganalytics.io/v1/workspaces/{workspace_id}/query"
)
# Azure AD token endpoint
_TOKEN_URL = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"


class SentinelClient:
    def __init__(self) -> None:
        # Direct shared-key auth
        self._workspace_id = os.getenv("SENTINEL_WORKSPACE_ID", "")
        self._api_key      = os.getenv("SENTINEL_API_KEY", "")

        # OAuth2 / service-principal auth
        self._client_id     = os.getenv("AZURE_CLIENT_ID", "")
        self._client_secret = os.getenv("AZURE_CLIENT_SECRET", "")
        self._tenant_id     = os.getenv("AZURE_TENANT_ID", "")

        self._access_token:  str   = ""
        self._token_expiry:  float = 0.0
        self._http: httpx.AsyncClient | None = None

    # ── Availability ──────────────────────────────────────────────────────

    @property
    def available(self) -> bool:
        """
        True if enough credentials are configured to make a query.
        Accepts either:
        - SENTINEL_WORKSPACE_ID + SENTINEL_API_KEY, or
        - SENTINEL_WORKSPACE_ID + AZURE_CLIENT_ID + AZURE_CLIENT_SECRET + AZURE_TENANT_ID
        """
        if not self._workspace_id:
            return False
        if self._api_key:
            return True
        return bool(self._client_id and self._client_secret and self._tenant_id)

    # ── HTTP client ───────────────────────────────────────────────────────

    def _client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(timeout=30)
        return self._http

    # ── Token management ──────────────────────────────────────────────────

    async def _get_bearer_token(self) -> str:
        """Obtain (or return cached) OAuth2 bearer token via client credentials."""
        if self._access_token and time.time() < self._token_expiry - 60:
            return self._access_token

        url = _TOKEN_URL.format(tenant_id=self._tenant_id)
        try:
            resp = await self._client().post(
                url,
                data={
                    "grant_type":    "client_credentials",
                    "client_id":     self._client_id,
                    "client_secret": self._client_secret,
                    "scope":         "https://api.loganalytics.io/.default",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            self._access_token = data["access_token"]
            self._token_expiry = time.time() + int(data.get("expires_in", 3600))
            return self._access_token
        except Exception as exc:
            logger.error("[sentinel] Token acquisition failed: %s", exc)
            return ""

    async def _auth_headers(self) -> dict[str, str]:
        if self._api_key:
            # Shared key auth (older workspaces)
            import hmac
            import hashlib
            import base64
            from datetime import datetime, timezone
            date_str = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
            string_to_hash = f"POST\napplication/json\n\nx-ms-date:{date_str}\n/api/query"
            decoded_key    = base64.b64decode(self._api_key)
            encoded_hash   = base64.b64encode(
                hmac.new(decoded_key, string_to_hash.encode("utf-8"), hashlib.sha256).digest()
            ).decode("utf-8")
            return {
                "Authorization":  f"SharedKey {self._workspace_id}:{encoded_hash}",
                "x-ms-date":      date_str,
                "Content-Type":   "application/json",
            }
        else:
            token = await self._get_bearer_token()
            return {
                "Authorization": f"Bearer {token}",
                "Content-Type":  "application/json",
            }

    # ── Core query ────────────────────────────────────────────────────────

    async def query(self, kql: str, timespan: str = "PT1H") -> list[dict]:
        """
        Execute a KQL query against the Log Analytics workspace.

        Args:
            kql:      KQL query string (without timespan — handled via timespan param).
            timespan: ISO 8601 duration string (default: "PT1H" = last 1 hour).

        Returns:
            List of row dicts from the first result table, or [] on error.
        """
        if not self.available:
            logger.debug("[sentinel] Client not configured — skipping query")
            return []

        url     = _LA_QUERY_URL.format(workspace_id=self._workspace_id)
        headers = await self._auth_headers()

        try:
            resp = await self._client().post(
                url,
                headers=headers,
                json={"query": kql, "timespan": timespan},
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "[sentinel] Query HTTP %s: %s",
                exc.response.status_code,
                exc.response.text[:200],
            )
            return []
        except Exception as exc:
            logger.error("[sentinel] Query failed: %s", exc)
            return []

        # Parse the tabular response
        tables = data.get("tables", [])
        if not tables:
            return []

        table   = tables[0]
        columns = [col["name"] for col in table.get("columns", [])]
        rows    = table.get("rows", [])

        return [dict(zip(columns, row)) for row in rows]

    # ── Technique detection check ──────────────────────────────────────────

    async def check_technique(
        self,
        technique_id: str,
        host: str | None = None,
    ) -> dict[str, Any]:
        """
        Query Microsoft Sentinel for evidence of a MITRE ATT&CK technique.

        Returns:
            {
                "detected":    bool,
                "alert_count": int,
                "events":      list[dict],
                "query_used":  str,
            }
        """
        host_filter = f'\n| where Computer == "{host}" or RemoteIP == "{host}"' if host else ""

        kql = (
            "union SecurityAlert, SecurityEvent, AzureDiagnostics, CommonSecurityLog\n"
            f'| where TimeGenerated >= ago(1h)\n'
            f'| where "{technique_id}" in (split(Techniques, ",")) '
            f'or tostring(ExtendedProperties) contains "{technique_id}" '
            f'or Description contains "{technique_id}" '
            f'or AlertName contains "{technique_id}"'
            f'{host_filter}\n'
            "| take 50"
        )

        try:
            events = await self.query(kql, timespan="PT1H")
        except Exception as exc:
            logger.error("[sentinel] check_technique error: %s", exc)
            events = []

        return {
            "detected":    len(events) > 0,
            "alert_count": len(events),
            "events":      events[:20],
            "query_used":  kql,
        }

    async def aclose(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()
