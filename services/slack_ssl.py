"""SSL context for Slack aiohttp clients (AsyncWebClient, Socket Mode WebSocket)."""

from __future__ import annotations

import logging
import ssl
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)


def aiohttp_ssl_context() -> Optional[ssl.SSLContext]:
    """
    SSL context for slack_sdk AsyncWebClient(ssl=...).

    - Default: use **certifi** CA bundle (fixes `unable to get local issuer certificate` on
      many Linux images where system store is empty or outdated).
    - ``SLACK_INSECURE_SSL=true``: disable verification (temporary testing only).
    - If certifi is missing and insecure is off, return None (aiohttp/openssl defaults).
    """
    if settings.slack_insecure_ssl:
        logger.warning(
            "SLACK_INSECURE_SSL is enabled: TLS certificate verification is OFF. "
            "Use only for short-lived local debugging; never in production."
        )
        return ssl._create_unverified_context()

    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        logger.warning(
            "certifi is not installed; Slack TLS may fail on hosts with weak system CAs. "
            "Install certifi or set SLACK_INSECURE_SSL=true only for local testing."
        )
        return None
