# FILE: agents/detect/siem/__init__.py
"""SIEM client registry — returns available clients."""
from __future__ import annotations

import logging
import os
import sys

# Ensure the siem/ directory is on sys.path so that splunk/elastic/sentinel
# can be imported whether this package is used as a package or via direct path.
_SIEM_DIR = os.path.dirname(os.path.abspath(__file__))
if _SIEM_DIR not in sys.path:
    sys.path.insert(0, _SIEM_DIR)

from splunk   import SplunkClient
from elastic  import ElasticClient
from sentinel import SentinelClient

logger = logging.getLogger(__name__)


def get_available_siem_clients() -> list:
    """
    Instantiate and return all SIEM clients whose credentials are configured.

    Returns a list containing zero or more of:
      SplunkClient, ElasticClient, SentinelClient

    If no SIEM is configured the list is empty — callers should handle that
    gracefully (e.g. score every technique as 0 / undetected).
    """
    clients = []

    for cls in (SplunkClient, ElasticClient, SentinelClient):
        try:
            instance = cls()
            if instance.available:
                clients.append(instance)
                logger.info("[siem-registry] %s is available", cls.__name__)
            else:
                logger.debug("[siem-registry] %s not configured", cls.__name__)
        except Exception as exc:
            logger.error("[siem-registry] Failed to instantiate %s: %s", cls.__name__, exc)

    if not clients:
        logger.warning(
            "[siem-registry] No SIEM clients configured. "
            "Set SPLUNK_URL+SPLUNK_TOKEN, ELASTIC_URL+ELASTIC_API_KEY, or "
            "SENTINEL_WORKSPACE_ID+AZURE_CLIENT_ID+AZURE_CLIENT_SECRET+AZURE_TENANT_ID."
        )

    return clients
