from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


# Default OAuth scopes for Slack Marketplace / distribution (bot only).
DEFAULT_SLACK_BOT_SCOPES = (
    "app_mentions:read,chat:write,im:history,im:read,im:write,users:read,commands"
)


class Settings(BaseSettings):
    # Slack OAuth (multi-workspace; App Directory)
    slack_client_id: str
    slack_client_secret: str
    slack_signing_secret: str
    """Used for OAuth HTTP callbacks; Socket Mode events do not require signature verification."""

    slack_app_token: str
    """App-level token for Socket Mode (xapp-..., connections:write)."""

    slack_redirect_uri: str
    """Must match a Redirect URL in Slack app settings (e.g. https://your.domain/slack/oauth_redirect)."""

    slack_bot_scopes: str = DEFAULT_SLACK_BOT_SCOPES
    """Comma-separated bot token scopes."""

    # Slack OAuth: FileInstallationStore (per-workspace bot tokens under this directory)
    slack_installation_base_dir: Path = Path("data/slack_installations")

    # Per-workspace LayerV API keys (encrypted JSON file; no SQLite)
    workspace_layerv_keys_path: Path = Path("data/workspace_layerv_keys.json")

    # OAuth state (CSRF) — short-lived; file-based under this directory
    oauth_state_dir: Path = Path("data/oauth_state")

    # HTTP server for OAuth only (Events still use Socket Mode)
    http_host: str = "0.0.0.0"
    http_port: int = 8080

    oauth_install_path: str = "/slack/install"
    oauth_redirect_path: str = "/slack/oauth_redirect"

    # Optional: redirect browser after successful/failed install (landing page)
    oauth_success_url: str | None = None
    oauth_failure_url: str | None = None

    # Temporary testing only: disable TLS verification for Slack API / Socket Mode (see services/slack_ssl.py).
    slack_insecure_ssl: bool = False

    # Claude API
    anthropic_api_key: str

    # LayerV API: optional fallback if a workspace has no key in DB (set by admins via DM /setkey)
    layerv_api_url: str = "https://api.layerv.xyz"
    layerv_api_key: str | None = None
    layerv_stats_url: str | None = None

    # Who may /setkey in Slack: on Enterprise Grid, always Enterprise org admin (user.enterprise_user.*).
    # On single-workspace teams, allow workspace Primary Owner / Owner / Admin if True; if False, only Grid org admins (or use LAYERV_API_KEY env).
    layerv_key_allow_workspace_admin_if_not_enterprise_grid: bool = True

    # Optional: Admin API fallback (user OAuth token with admin.roles:read, org-installed app).
    # Use when you rely on admin.roles.listAssignments instead of or in addition to users.info enterprise_user flags.
    slack_admin_user_token: str | None = None
    use_admin_roles_api_fallback: bool = False
    """If True and slack_admin_user_token is set, try admin.roles.listAssignments to confirm org-level roles."""

    slack_org_admin_role_ids: str = ""
    """Comma-separated role_id values from admin.roles.list (e.g. Organization Admin). Required for Admin API fallback."""

    # QURL defaults
    qurl_default_expires_in: str = "30m"

    # Encryption secret (kept for compatibility if you reintroduce encrypted local fields)
    encryption_secret: str = "qurl-bot-slack-default-secret"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
