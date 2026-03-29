"""
Web client — HTTP fetches and search for agents.
All outbound internet requests from agents go through here.
"""
import os
import logging
import httpx

logger = logging.getLogger(__name__)

BRAVE_API_KEY = os.getenv("BRAVE_API_KEY", "")
USER_AGENT    = "SecuNet-Agent/1.0 (security research; authorized)"
TIMEOUT       = float(os.getenv("WEB_TIMEOUT", "15"))


async def fetch(url: str, headers: dict | None = None) -> str:
    """Fetch a URL and return the response text."""
    hdrs = {"User-Agent": USER_AGENT, **(headers or {})}
    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
        try:
            r = await client.get(url, headers=hdrs)
            r.raise_for_status()
            return r.text
        except Exception as exc:
            logger.error("fetch(%s) failed: %s", url, exc)
            return ""


async def fetch_json(url: str, headers: dict | None = None) -> dict | list | None:
    """Fetch a URL and return parsed JSON."""
    hdrs = {"User-Agent": USER_AGENT, **(headers or {})}
    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
        try:
            r = await client.get(url, headers=hdrs)
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            logger.error("fetch_json(%s) failed: %s", url, exc)
            return None


async def search(query: str, count: int = 5) -> list[dict]:
    """
    Web search via Brave Search API.
    Returns list of {"title": ..., "url": ..., "description": ...}.
    Falls back to empty list if BRAVE_API_KEY not set.
    """
    if not BRAVE_API_KEY:
        logger.warning("BRAVE_API_KEY not set — web search unavailable")
        return []
    url = "https://api.search.brave.com/res/v1/web/search"
    params = f"?q={httpx.URL('', params={'q': query, 'count': count}).params}"
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.get(
                url,
                params={"q": query, "count": count},
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip",
                    "X-Subscription-Token": BRAVE_API_KEY,
                },
            )
            r.raise_for_status()
            data = r.json()
            results = data.get("web", {}).get("results", [])
            return [
                {"title": r.get("title", ""), "url": r.get("url", ""), "description": r.get("description", "")}
                for r in results
            ]
    except Exception as exc:
        logger.error("search(%r) failed: %s", query, exc)
        return []
