# qurl-bot-slack

Generates secure proxy links via the LayerV QURL API in Slack. Supports **OAuth multi-workspace install** (for [Slack Marketplace](https://api.slack.com/docs/slack-apps-checklist) style distribution), **on-disk file storage** for OAuth installs and per-workspace LayerV keys (no SQLite), and **Socket Mode** for events.

## Features

- Parses user messages for URLs and intent
- Calls the LayerV API to create QURLs
- Configurable expiry
- **Per-workspace** LayerV API key: manage with `/setkey`, `/mykey`, `/delkey` in a **DM with the bot** only; **no key operations in channels** (anti-leak).  
  - **Enterprise Grid**: must be **Enterprise organization** Primary Owner / Owner / Admin (`enterprise_user` in `users.info`); workspace-only admin is not enough.  
  - **Non–Enterprise Grid**: by default, workspace Primary Owner / Owner / Admin may configure (disable with `LAYERV_KEY_ALLOW_WORKSPACE_ADMIN_IF_NOT_ENTERPRISE_GRID=false`).  
  - Optional server-side `LAYERV_API_KEY` as fallback when no workspace key is stored.  
  - Optional `admin.roles.listAssignments` (`admin.roles:read` user token + `SLACK_ORG_ADMIN_ROLE_IDS`) — see `.env.example`.

## Requirements

- Python 3.10+
- Slack app with **Socket Mode** and **OAuth** (distribution / App Directory)
- For OAuth install/callback only (**not** Events HTTP): **testing** may use **`http://`** (e.g. localhost or IP) where Slack allows it; **production / App Directory** should use a public **HTTPS** reverse proxy to this process’s `HTTP_HOST`/`HTTP_PORT`.

## Quick start

### 1. Slack app (api.slack.com/apps)

1. **OAuth & Permissions → Bot Token Scopes** (aligned with default `SLACK_BOT_SCOPES`):  
   `app_mentions:read`, `chat:write`, `im:history`, `im:read`, `im:write`, `users:read`, `commands`

2. **Socket Mode**: enable and create an App-Level Token (`connections:write`) → `SLACK_APP_TOKEN`.

3. **Event Subscriptions**: with Socket Mode enabled, subscribe to:  
   `app_home_opened`, `app_mention`, `message.im`

4. **Slash Commands**: register `/setkey`, `/mykey`, `/delkey` as needed (prefix with app name for Marketplace to reduce collisions).

5. **OAuth & Permissions → Redirect URLs**  
   Add a URL that **exactly** matches `SLACK_REDIRECT_URI` in `.env`, e.g.:  
   `https://your.domain/slack/oauth_redirect`

6. **Manage distribution**: enable public distribution and complete Slack’s checklist (listing also needs landing page, privacy policy, support, etc.).

### 2. Environment

```bash
cp .env.example .env
```

Required variables are documented in `.env.example`. **`SLACK_REDIRECT_URI` must match Slack’s Redirect URLs exactly** (including `http` vs `https`). Use **`http://`** for local/dev testing if Slack accepts it; use **`https://your.domain`** in production and terminate TLS at your reverse proxy.

### 3. Install and run

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
python app.py
```

The process:

- Serves **`/slack/install`** and **`/slack/oauth_redirect`** on `HTTP_HOST`/`HTTP_PORT` (OAuth)
- Connects to Slack via Socket Mode for events

Install URL (browser): `https://your.domain/slack/install` in production; during testing you may use `http://127.0.0.1:8080/slack/install` or `http://IP:PORT/slack/install` if it matches `SLACK_REDIRECT_URI` (same scheme/host/port as configured in Slack).

### 4. Data

- **`SLACK_INSTALLATION_BASE_DIR`** (default `data/slack_installations`): OAuth installs (bot tokens), via `slack_sdk` `FileInstallationStore`.
- **`WORKSPACE_LAYERV_KEYS_PATH`** (default `data/workspace_layerv_keys.json`): encrypted LayerV API keys per Slack workspace (`/setkey`).
- **`OAUTH_STATE_DIR`**: short-lived OAuth `state` files (CSRF).

**Migrating from SQLite builds:** older deployments stored OAuth + LayerV keys in `data/slack_app.db`. Current code does not read that file. After upgrade, **reinstall the app** to each workspace (OAuth) and run **`/setkey`** again in DM to restore LayerV keys.

**Why `pysqlite3-binary`:** `slack-bolt` imports OAuth code that loads the stdlib `sqlite3` module at startup, even when using file-based installation stores. If your Python was built without `_sqlite3` (e.g. `/usr/local` without `sqlite-devel`), `app.py` registers `pysqlite3` as `sqlite3` before any Bolt import. Normal Python builds ignore this package.

**Slack TLS / `SSLCertVerificationError`:** Slack clients use **aiohttp**, which does not automatically use **certifi**. The app sets `AsyncWebClient(ssl=ssl.create_default_context(cafile=certifi.where()))` by default so certificate verification works on hosts with weak system CA stores. Use **`SLACK_INSECURE_SSL=true`** only as a last resort for temporary testing.

## Example usage

DM the bot or `@mention` it in a channel:

```
google.com please give me a proxy link
@qurl-bot-slack https://github.com proxy link 7 days
```

## Layout (partial)

```
├── app.py                 # entrypoint
├── config.py              # settings
├── adapters/slack_app.py  # Bolt AsyncApp, OAuth, Socket Mode
├── core/bot_core.py      # QURL logic
├── services/              # LayerV, AI, parsing, i18n
└── requirements.txt
```

## Notes

- You need a valid **LayerV API key** path and **Anthropic API key** (see `.env`).
- For Marketplace listing, disclose LLM usage and data retention per Slack’s checklist.
- If you change bot scopes or slash command names, update the Slack app and this repo’s docs.
