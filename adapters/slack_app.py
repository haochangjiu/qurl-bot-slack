"""
Slack adapter for qurl-bot-slack.

OAuth (multi-workspace) + file installation store + Socket Mode for events.
"""

import asyncio
import logging
import re

from aiohttp import web
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp
from slack_bolt.oauth.async_oauth_settings import AsyncOAuthSettings
from slack_sdk.oauth.installation_store.file import FileInstallationStore
from slack_sdk.oauth.state_store.file import FileOAuthStateStore
from slack_sdk.web.async_client import AsyncWebClient

from config import settings
from services.slack_ssl import aiohttp_ssl_context
from core.bot_core import (
    process_message,
    analyze_message,
    build_proxy_reply,
    _dashboard_reply,
    handle_setkey,
    handle_mykey,
    handle_delkey,
    preprocess_text,
    detect_language,
)
from services.workspace_key_store import init_workspace_key_store
from services.slack_entitlements import classify_layerv_key_eligibility
from services.i18n import get_message

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _scope_list() -> list[str]:
    return [s.strip() for s in settings.slack_bot_scopes.split(",") if s.strip()]


def build_slack_app() -> AsyncApp:
    settings.slack_installation_base_dir.mkdir(parents=True, exist_ok=True)
    settings.oauth_state_dir.mkdir(parents=True, exist_ok=True)
    init_workspace_key_store()

    installation_store = FileInstallationStore(
        base_dir=str(settings.slack_installation_base_dir),
        client_id=settings.slack_client_id,
        logger=logger,
    )
    state_store = FileOAuthStateStore(
        expiration_seconds=600,
        base_dir=str(settings.oauth_state_dir),
        client_id=settings.slack_client_id,
        logger=logger,
    )

    oauth_settings = AsyncOAuthSettings(
        client_id=settings.slack_client_id,
        client_secret=settings.slack_client_secret,
        scopes=_scope_list(),
        redirect_uri=settings.slack_redirect_uri,
        install_path=settings.oauth_install_path,
        redirect_uri_path=settings.oauth_redirect_path,
        installation_store=installation_store,
        installation_store_bot_only=True,
        state_store=state_store,
        success_url=settings.oauth_success_url,
        failure_url=settings.oauth_failure_url,
    )

    ssl_ctx = aiohttp_ssl_context()
    # Always pass explicit ssl when we have a context (certifi or insecure); avoids broken system CA on some hosts.
    bolt_client = AsyncWebClient(ssl=ssl_ctx) if ssl_ctx is not None else None

    app = AsyncApp(
        signing_secret=settings.slack_signing_secret,
        oauth_settings=oauth_settings,
        client=bolt_client,
    )
    register_slack_handlers(app)
    return app


def _preprocess_slack(text: str) -> str:
    return preprocess_text(text)


def _parse_command(text: str) -> tuple[str | None, str]:
    t = text.strip()
    if t.startswith("/setkey"):
        arg = t[7:].strip()
        return ("setkey", arg)
    if t.startswith("/mykey"):
        return ("mykey", "")
    if t.startswith("/delkey"):
        return ("delkey", "")
    return (None, "")


_bot_user_id: str | None = None


async def _get_bot_user_id(client) -> str:
    global _bot_user_id
    if _bot_user_id is None:
        auth = await client.auth_test()
        _bot_user_id = auth["user_id"]
    return _bot_user_id


async def _get_slack_user_info(client, user_id: str) -> dict:
    info: dict = {"tz": None, "email": None}
    if not client:
        return info
    try:
        response = await client.users_info(user=user_id)
        if response.get("ok") and response.get("user"):
            user_data = response["user"]
            info["tz"] = user_data.get("tz")
            info["email"] = user_data.get("profile", {}).get("email")
    except Exception as e:
        logger.warning(f"Failed to get user info for {user_id}: {e}")
    return info


async def _is_im_channel(client, channel_id: str) -> bool:
    try:
        r = await client.conversations_info(channel=channel_id)
        if not r.get("ok"):
            return False
        ch = r.get("channel") or {}
        return bool(ch.get("is_im"))
    except Exception as e:
        logger.warning(f"conversations_info failed for {channel_id}: {e}")
        return False


def _layerv_key_denial_message(kind: str, lang: str) -> str:
    if kind == "enterprise_org_admin_required":
        return get_message("key_enterprise_org_admin_only", lang)
    return get_message("key_admin_only", lang)


def _slash_response_mrkdwn_blocks(text: str) -> list[dict]:
    """Slack slash-command ``text=`` is often plain; use blocks + mrkdwn for *bold* etc."""
    return [{"type": "section", "text": {"type": "mrkdwn", "text": text}}]


def _team_id(event_or_cmd: dict, context_team_id: str | None = None) -> str | None:
    if context_team_id:
        return context_team_id
    return (
        event_or_cmd.get("team")
        or event_or_cmd.get("team_id")
        or event_or_cmd.get("view", {}).get("team_id")
    )


async def _send_dm(client, user: str, text: str):
    resp = await client.conversations_open(users=user)
    dm_channel = resp["channel"]["id"]
    await client.chat_postMessage(channel=dm_channel, text=text)


def _extract_slack_mentions(text: str) -> list[str]:
    return re.findall(r"<@([A-Z0-9]+)>", text)


def register_slack_handlers(app: AsyncApp) -> None:
    @app.command("/setkey")
    async def handle_setkey_slack(ack, command, client, respond):
        await ack()
        user_id = command["user_id"]
        team_id = command.get("team_id")
        channel_id = command["channel_id"]
        lang = detect_language(command.get("text") or "")
        if not await _is_im_channel(client, channel_id):
            _dm_only = get_message("key_ops_dm_only", lang)
            await respond(
                response_type="ephemeral",
                blocks=_slash_response_mrkdwn_blocks(_dm_only),
                text=_dm_only,
            )
            return
        lvl = await classify_layerv_key_eligibility(client, user_id)
        if lvl != "ok":
            _deny = _layerv_key_denial_message(lvl, lang)
            await respond(
                response_type="ephemeral",
                blocks=_slash_response_mrkdwn_blocks(_deny),
                text=_deny,
            )
            return
        api_key = (command.get("text") or "").strip()
        logger.info(f"Slack setkey from admin {user_id}, key_len={len(api_key)}")
        msg, out_lang = await handle_setkey(api_key, team_id, True, lang)
        await respond(
            blocks=_slash_response_mrkdwn_blocks(msg),
            text=msg,
        )

    @app.command("/mykey")
    async def handle_mykey_slack(ack, command, client, respond):
        await ack()
        user_id = command["user_id"]
        team_id = command.get("team_id")
        channel_id = command["channel_id"]
        lang = detect_language(command.get("text") or "")
        if not await _is_im_channel(client, channel_id):
            _dm_only = get_message("key_ops_dm_only", lang)
            await respond(
                response_type="ephemeral",
                blocks=_slash_response_mrkdwn_blocks(_dm_only),
                text=_dm_only,
            )
            return
        lvl = await classify_layerv_key_eligibility(client, user_id)
        if lvl != "ok":
            _deny = _layerv_key_denial_message(lvl, lang)
            await respond(
                response_type="ephemeral",
                blocks=_slash_response_mrkdwn_blocks(_deny),
                text=_deny,
            )
            return
        user_info = await _get_slack_user_info(client, user_id)
        msg, _ = await handle_mykey(team_id, True, user_info["tz"], lang)
        await respond(blocks=_slash_response_mrkdwn_blocks(msg), text=msg)

    @app.command("/delkey")
    async def handle_delkey_slack(ack, command, client, respond):
        await ack()
        user_id = command["user_id"]
        team_id = command.get("team_id")
        channel_id = command["channel_id"]
        lang = detect_language(command.get("text") or "")
        if not await _is_im_channel(client, channel_id):
            _dm_only = get_message("key_ops_dm_only", lang)
            await respond(
                response_type="ephemeral",
                blocks=_slash_response_mrkdwn_blocks(_dm_only),
                text=_dm_only,
            )
            return
        lvl = await classify_layerv_key_eligibility(client, user_id)
        if lvl != "ok":
            _deny = _layerv_key_denial_message(lvl, lang)
            await respond(
                response_type="ephemeral",
                blocks=_slash_response_mrkdwn_blocks(_deny),
                text=_deny,
            )
            return
        msg, _ = await handle_delkey(team_id, True, lang)
        await respond(blocks=_slash_response_mrkdwn_blocks(msg), text=msg)

    @app.event("app_mention")
    async def handle_app_mention(event, say, client, context=None):
        text = event.get("text", "")
        user = event.get("user")
        team_id = _team_id(event, getattr(context, "team_id", None) if context else None)

        bot_id = await _get_bot_user_id(client)
        mentioned_users = [
            uid for uid in _extract_slack_mentions(text)
            if uid != bot_id
        ]

        clean_text = _preprocess_slack(text)
        if not clean_text:
            await say(f"<@{user}> {get_message('empty_input', 'en')}")
            return

        user_info = await _get_slack_user_info(client, user)
        user_tz = user_info["tz"]
        lang_hint = detect_language(clean_text)
        if user_info["email"]:
            logger.info(f"Slack request from {user} (email: {user_info['email']}): {clean_text}")
        else:
            logger.info(f"Slack mention from {user}: {clean_text}")

        cmd, arg = _parse_command(clean_text)
        if cmd:
            await say(f"<@{user}> {get_message('key_ops_dm_only', lang_hint)}")
            return

        analysis = await analyze_message(clean_text, user, team_id)
        if "dashboard" in analysis:
            await say(f"<@{user}> {_dashboard_reply(analysis['lang'])}")
            return
        if "error" in analysis:
            await say(f"<@{user}> {analysis['error']}")
            return

        lang = analysis["lang"]
        dm_targets = mentioned_users if mentioned_users else [user]

        success = []
        for target in dm_targets:
            reply, _ = await build_proxy_reply(
                analysis["urls"], analysis["api_key"], analysis["expires_in"],
                analysis["reason"], lang, user, user_tz=user_tz,
            )
            try:
                if target == user:
                    await _send_dm(client, target, reply)
                else:
                    target_info = await _get_slack_user_info(client, target)
                    if target_info["email"]:
                        logger.info(f"Sending proxy to {target} (email: {target_info['email']})")
                    header = get_message("dm_proxy_for_you", lang, from_user=f"<@{user}>")
                    await _send_dm(client, target, f"{header}\n{reply}")
                success.append(target)
            except Exception as e:
                logger.warning(f"Cannot DM Slack user {target}: {e}")

        if success:
            if mentioned_users:
                mentions = " ".join(f"<@{u}>" for u in success)
                await say(f"<@{user}> {get_message('dm_sent_to_users', lang, users=mentions)}")
            else:
                await say(f"<@{user}> {get_message('dm_sent', lang)}")
        else:
            await say(f"<@{user}> {get_message('dm_failed', lang)}")

    @app.event("message")
    async def handle_direct_message(event, say, client, context=None):
        if event.get("channel_type") != "im":
            return
        if event.get("subtype"):
            return
        if re.search(r"<@[A-Z0-9]+>", event.get("text", "")):
            return

        text = event.get("text", "")
        user = event.get("user")
        team_id = _team_id(event, getattr(context, "team_id", None) if context else None)
        clean_text = _preprocess_slack(text)
        if not clean_text:
            await say(f"<@{user}> {get_message('empty_input', 'en')}")
            return

        user_info = await _get_slack_user_info(client, user)
        lang = detect_language(clean_text)
        if user_info["email"]:
            logger.info(f"Slack DM from {user} (email: {user_info['email']}): {clean_text}")
        else:
            logger.info(f"Slack DM from {user}: {clean_text}")

        cmd, arg = _parse_command(clean_text)
        if cmd:
            lvl = await classify_layerv_key_eligibility(client, user)
            if lvl != "ok":
                await say(f"<@{user}> {_layerv_key_denial_message(lvl, lang)}")
                return
            if cmd == "setkey":
                msg, _ = await handle_setkey(arg, team_id, True, lang)
            elif cmd == "mykey":
                msg, _ = await handle_mykey(team_id, True, user_info["tz"], lang)
            else:
                msg, _ = await handle_delkey(team_id, True, lang)
            await say(f"<@{user}> {msg}")
            return

        reply, _ = await process_message(clean_text, user, team_id, user_tz=user_info["tz"])
        await say(f"<@{user}> {reply}")

    @app.event("app_home_opened")
    async def handle_app_home_opened(client, event):
        try:
            await client.views_publish(
                user_id=event["user"],
                view={
                    "type": "home",
                    "blocks": [
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": f"{get_message('welcome_title', 'en')} / {get_message('welcome_title', 'zh')}",
                            },
                        },
                        {"type": "divider"},
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": get_message("welcome_body", "en"),
                            },
                        },
                        {"type": "divider"},
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": get_message("welcome_body", "zh"),
                            },
                        },
                    ],
                },
            )
        except Exception as e:
            err_str = str(e)
            if "not_enabled" in err_str.lower():
                logger.debug(
                    "App Home not enabled. Enable at: https://api.slack.com/apps > Your App > App Home"
                )
            else:
                logger.warning(f"Failed to publish app home: {e}")


async def run_slack_oauth_server(bolt_app: AsyncApp) -> web.AppRunner:
    """Start aiohttp app for /slack/install and /slack/oauth_redirect only."""
    srv = bolt_app.server(
        port=settings.http_port,
        path="/slack/events",
        host=settings.http_host,
    )
    runner = web.AppRunner(srv.web_app)
    await runner.setup()
    site = web.TCPSite(runner, settings.http_host, settings.http_port)
    await site.start()
    logger.info(
        "OAuth HTTP server on %s:%s (install=%s, callback=%s)",
        settings.http_host,
        settings.http_port,
        settings.oauth_install_path,
        settings.oauth_redirect_path,
    )
    return runner


async def run_slack() -> None:
    """Run OAuth endpoints + Socket Mode until shutdown."""
    bolt_app = build_slack_app()
    runner = await run_slack_oauth_server(bolt_app)
    try:
        # Socket Mode must use the same AsyncWebClient (and ssl=) as Bolt — see slack_sdk SocketModeClient.ws_connect
        handler = AsyncSocketModeHandler(
            bolt_app,
            settings.slack_app_token,
            web_client=bolt_app.client,
        )
        logger.info("Starting qurl-bot-slack (Socket Mode + OAuth)...")
        await handler.start_async()
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(run_slack())
