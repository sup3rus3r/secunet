# FILE: agents/detect/siem/elastic.py
"""
Elasticsearch/Elastic Security client.
Queries for detections of a specific technique.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class ElasticClient:
    def __init__(self) -> None:
        self._url     = os.getenv("ELASTIC_URL", "").rstrip("/")
        self._api_key = os.getenv("ELASTIC_API_KEY", "")
        self._http: httpx.AsyncClient | None = None

    # ── Lazy HTTP client ──────────────────────────────────────────────────

    def _client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                base_url=self._url,
                headers={
                    "Authorization": f"ApiKey {self._api_key}",
                    "Content-Type":  "application/json",
                    "kbn-xsrf":      "true",
                },
                verify=False,
                timeout=30,
            )
        return self._http

    # ── Availability ──────────────────────────────────────────────────────

    @property
    def available(self) -> bool:
        """True if ELASTIC_URL and ELASTIC_API_KEY are configured."""
        return bool(self._url and self._api_key)

    # ── Core search ───────────────────────────────────────────────────────

    async def search(
        self,
        query: dict,
        index: str = ".alerts-security*",
    ) -> dict:
        """
        POST a DSL query to Elasticsearch and return the full response dict.

        Args:
            query:  Elasticsearch DSL query body (dict).
            index:  Index pattern to search (default: Elastic Security alerts).

        Returns:
            Raw Elasticsearch response dict, or {} on error.
        """
        if not self.available:
            logger.debug("[elastic] Client not configured — skipping search")
            return {}

        client = self._client()
        try:
            resp = await client.post(
                f"/{index}/_search",
                json=query,
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "[elastic] Search HTTP %s: %s",
                exc.response.status_code,
                exc.response.text[:200],
            )
            return {}
        except Exception as exc:
            logger.error("[elastic] Search failed: %s", exc)
            return {}

    # ── Technique detection check ──────────────────────────────────────────

    async def check_technique(
        self,
        technique_id: str,
        host: str | None = None,
    ) -> dict[str, Any]:
        """
        Query Elastic Security alerts index for evidence of a MITRE technique.

        Returns:
            {
                "detected":    bool,
                "alert_count": int,
                "events":      list[dict],
                "query_used":  str,
            }
        """
        # Build must clauses
        must_clauses: list[dict] = [
            {
                "bool": {
                    "should": [
                        {"term": {"threat.technique.id":           technique_id}},
                        {"term": {"rule.threat.technique.id":      technique_id}},
                        {"term": {"kibana.alert.rule.parameters.threat.technique.id": technique_id}},
                        {"match_phrase": {"message": technique_id}},
                    ],
                    "minimum_should_match": 1,
                }
            },
            {
                "range": {
                    "@timestamp": {"gte": "now-1h", "lte": "now"}
                }
            },
        ]

        if host:
            must_clauses.append({
                "bool": {
                    "should": [
                        {"term": {"host.ip":           host}},
                        {"term": {"host.name":         host}},
                        {"term": {"destination.ip":    host}},
                        {"term": {"source.ip":         host}},
                    ],
                    "minimum_should_match": 1,
                }
            })

        dsl_query: dict = {
            "size": 50,
            "query": {
                "bool": {"must": must_clauses}
            },
            "_source": [
                "@timestamp",
                "rule.name",
                "threat.technique.id",
                "threat.technique.name",
                "host.name",
                "host.ip",
                "kibana.alert.severity",
                "signal.rule.name",
                "message",
            ],
        }

        resp = await self.search(dsl_query)
        hits = resp.get("hits", {}).get("hits", [])

        events = [h.get("_source", {}) for h in hits]
        return {
            "detected":    len(events) > 0,
            "alert_count": len(events),
            "events":      events[:20],
            "query_used":  f"Elastic DSL for {technique_id}" + (f" on {host}" if host else ""),
        }

    async def aclose(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()
