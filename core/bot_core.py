"""
qurl-bot-slack: Slack bot logic for QURL proxy generation.

Handles message analysis, URL extraction, QURL creation.
Returns message content to be sent by the Slack adapter.
"""

import logging
import re

from config import settings
from services.layerv import layerv_client, InvalidApiKeyError
from services.ai_analyzer import ai_analyzer
from services.url_parser import extract_urls, normalize_url, is_valid_url
from services.i18n import get_message
from services.time_utils import format_utc_to_local, format_expires_in_display
import services.workspace_key_store as workspace_key_store

logger = logging.getLogger(__name__)


def resolve_layerv_api_key(team_id: str | None) -> str | None:
    """Workspace-specific key in file store, else optional env LAYERV_API_KEY fallback."""
    if team_id:
        k = workspace_key_store.get_api_key(team_id)
        if k:
            return k
    return settings.layerv_api_key


def has_layerv_api_key(team_id: str | None) -> bool:
    return bool(resolve_layerv_api_key(team_id))


def preprocess_text(text: str) -> str:
    """Strip Slack link formatting and mentions from message text."""
    text = re.sub(r"<(https?://[^|>]+)\|[^>]+>", r"\1", text)
    text = re.sub(r"<(https?://[^>]+)>", r"\1", text)
    text = re.sub(r"<@[A-Z0-9]+>", "", text)
    return text.strip()


def detect_language(text: str) -> str:
    """Simple language detection based on character analysis."""
    if re.search(r"[\u4e00-\u9fff]", text):
        return "zh"
    return "en"


# English + Chinese tokens for lightweight dashboard-intent detection (not i18n strings).
_QURL_DASHBOARD_KEYWORDS = [
    "dashboard", "stats", "stat", "status", "portal", "console",
    "状态", "统计", "面板", "控制台",
]
_QURL_ACCESS_KEYWORDS_ZH = ["查看", "访问", "打开", "给我", "我要", "链接", "连接", "地址"]

_KNOWN_SITE_NAMES = [
    "google", "youtube", "github", "amazon", "facebook", "twitter",
    "instagram", "netflix", "reddit", "linkedin", "baidu", "taobao",
    "chatgpt", "openai", "wikipedia", "spotify", "tiktok", "slack",
    "discord", "notion", "figma", "vercel", "stackoverflow",
    "谷歌", "油管", "亚马逊", "脸书", "推特", "百度", "淘宝", "维基百科",
]


def _has_external_url_or_site(text: str) -> bool:
    """Check if text contains URLs, domains, or website names other than 'qurl'."""
    t = re.sub(r"qurl", "", text.lower())
    if re.search(r"https?://", t):
        return True
    if re.search(r"\b[\w-]+\.(?:com|org|net|io|ai|xyz|dev|co|me|cn|uk|jp)\b", t):
        return True
    return any(site in t for site in _KNOWN_SITE_NAMES)


def _is_qurl_dashboard_request(text: str) -> bool:
    """Check if the user is asking for the QURL dashboard/stats URL."""
    t = text.lower().strip()
    if "qurl" not in t:
        return False
    if _has_external_url_or_site(t):
        return False
    if any(kw in t for kw in _QURL_DASHBOARD_KEYWORDS):
        return True
    if any(kw in t for kw in _QURL_ACCESS_KEYWORDS_ZH):
        return True
    return False


async def analyze_message(text: str, user_id: str, team_id: str | None) -> dict:
    """
    Analyze message: AI analysis + URL extraction + API key validation.
    Call once, then use build_proxy_reply() per recipient.

    Returns dict:
      success   → {'urls', 'api_key', 'expires_in', 'reason', 'lang'}
      dashboard → {'dashboard': True, 'lang'}
      error     → {'error', 'lang'}
    """
    lang = "en"

    if not text:
        return {"error": get_message("empty_input", lang), "lang": lang}

    if _is_qurl_dashboard_request(text):
        lang = detect_language(text)
        return {"dashboard": True, "lang": lang}

    if not has_layerv_api_key(team_id):
        lang = detect_language(text)
        return {"error": get_message("no_api_key_workspace", lang), "lang": lang}

    try:
        analysis = await ai_analyzer.analyze(text)
        lang = analysis.language

        logger.info(
            f"AI analysis: lang={lang}, urls={analysis.urls}, "
            f"expires_in={analysis.expires_in}"
        )

        extracted_urls = extract_urls(text)
        combined = analysis.urls + extracted_urls
        normalized = [normalize_url(u) for u in combined]
        all_urls = list(dict.fromkeys(normalized))

        if not all_urls:
            return {"error": get_message("no_url_detected", lang), "lang": lang}

        api_key = resolve_layerv_api_key(team_id)
        if not api_key:
            return {"error": get_message("no_api_key_workspace", lang), "lang": lang}

        return {
            "urls": all_urls,
            "api_key": api_key,
            "expires_in": analysis.expires_in,
            "reason": analysis.reason,
            "lang": lang,
        }
    except Exception as e:
        logger.error(f"Error analyzing message: {e}")
        return {"error": get_message("processing_error", lang, error=str(e)), "lang": lang}


async def build_proxy_reply(
    urls: list[str],
    api_key: str,
    expires_in: str,
    reason: str,
    lang: str,
    user_id: str,
    user_tz: str | None = None,
) -> tuple[str, str]:
    """
    Generate unique QURL proxy links for the given URLs.
    Each call creates new links — call once per recipient for unique links.

    Returns (formatted_message, language).
    """
    results = []
    errors = []

    for url in urls:
        if not is_valid_url(url):
            errors.append(get_message("invalid_url", lang, url=url))
            continue

        try:
            qurl_response = await layerv_client.create_qurl(
                api_key=api_key,
                target_url=url,
                expires_in=expires_in,
                description=reason or f"Generated via qurl-bot-slack for user {user_id}",
            )
            if user_tz:
                expires_display = format_utc_to_local(qurl_response.expires_at, user_tz=user_tz)
            else:
                expires_display = format_expires_in_display(expires_in, lang)
            results.append(
                {
                    "original_url": url,
                    "qurl_link": qurl_response.qurl_link,
                    "expires_at": expires_display,
                }
            )
        except InvalidApiKeyError:
            logger.error(f"Invalid API key for slack user {user_id}")
            return get_message("invalid_api_key", lang), lang
        except Exception as e:
            logger.error(f"Failed to create QURL for {url}: {e}")
            errors.append(get_message("failed_item", lang, url=url, error=str(e)))

    parts = []
    if results:
        parts.append(get_message("proxy_generated_header", lang))
        for r in results:
            parts.append(
                get_message(
                    "proxy_item",
                    lang,
                    original_url=r["original_url"],
                    qurl_link=r["qurl_link"],
                    expires_at=r["expires_at"],
                )
            )
    if errors:
        parts.append(get_message("failed_header", lang))
        parts.extend([f"\n{e}" for e in errors])

    return "".join(parts), lang


async def process_message(
    text: str,
    user_id: str,
    team_id: str | None,
    user_tz: str | None = None,
) -> tuple[str, str]:
    """Single-user convenience wrapper: analyze once + build proxies."""
    result = await analyze_message(text, user_id, team_id)
    if "dashboard" in result:
        return _dashboard_reply(result["lang"]), result["lang"]
    if "error" in result:
        return result["error"], result["lang"]
    return await build_proxy_reply(
        result["urls"], result["api_key"], result["expires_in"],
        result["reason"], result["lang"], user_id, user_tz,
    )


def _dashboard_reply(lang: str) -> str:
    """Return the QURL dashboard URL or a not-configured message."""
    if settings.layerv_stats_url:
        return get_message("qurl_dashboard", lang, url=settings.layerv_stats_url)
    return get_message("qurl_dashboard_not_configured", lang)


async def handle_setkey(
    api_key: str,
    team_id: str | None,
    is_admin: bool,
    lang: str,
) -> tuple[str, str]:
    """Store LayerV key for team_id. DM-only and eligibility are enforced in the Slack adapter."""
    if not team_id:
        return get_message("no_team_context", lang), lang
    if not is_admin:
        return get_message("key_admin_only", lang), lang
    key = api_key.strip()
    if not key:
        return get_message("setkey_usage", lang), lang
    if not await layerv_client.verify_api_key(key):
        return get_message("setkey_invalid", lang), lang
    try:
        workspace_key_store.set_api_key(team_id, key)
        return get_message("setkey_success", lang), lang
    except Exception as e:
        logger.error(f"setkey store error: {e}")
        return get_message("setkey_error", lang, error=str(e)), lang


async def handle_mykey(
    team_id: str | None,
    is_admin: bool,
    user_tz: str | None,
    lang: str,
) -> tuple[str, str]:
    """Show stored key prefix for authorized callers (eligibility checked in the adapter)."""
    if not is_admin:
        return get_message("key_admin_only", lang), lang
    if not team_id:
        return get_message("no_team_context", lang), lang

    info = workspace_key_store.get_key_info(team_id)
    if info:
        updated = info["updated_at"] or "-"
        try:
            updated = format_utc_to_local(updated, user_tz=user_tz) if updated.endswith("Z") or "+" in updated else updated
        except Exception:
            pass
        return (
            get_message(
                "workspace_mykey_info",
                lang,
                prefix=info["api_key_prefix"],
                updated_at=updated,
            ),
            lang,
        )
    if settings.layerv_api_key:
        prefix = settings.layerv_api_key[:8] + "..." if len(settings.layerv_api_key) > 8 else settings.layerv_api_key
        return get_message("mykey_fallback_server_env", lang, prefix=prefix), lang
    return get_message("mykey_none_workspace", lang), lang


async def handle_delkey(team_id: str | None, is_admin: bool, lang: str) -> tuple[str, str]:
    """Remove stored workspace key. Caller must be authorized (adapter checks entitlements)."""
    if not team_id:
        return get_message("no_team_context", lang), lang
    if not is_admin:
        return get_message("key_admin_only", lang), lang
    if workspace_key_store.delete_api_key(team_id):
        return get_message("delkey_success", lang), lang
    return get_message("delkey_none_workspace", lang), lang
