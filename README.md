# qurl-bot-slack

Generates secure proxy links via the LayerV QURL API in Slack. Supports **OAuth multi-workspace install** (for [Slack Marketplace](https://api.slack.com/docs/slack-apps-checklist) style distribution), **SQLite** for installation data, and **Socket Mode** for events.

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
- Public **HTTPS** reverse proxy to this process’s HTTP port (OAuth install/callback only — **not** Events HTTP)

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

Required variables are documented in `.env.example`. In production use **HTTPS** for `SLACK_REDIRECT_URI` and proxy `https://your.domain` to this service’s `HTTP_HOST`/`HTTP_PORT`.

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

Install URL (browser): `https://your.domain/slack/install` (same host as Redirect URL; HTTPS in production).

### 4. Data

- **`SQLITE_DATABASE_PATH`** (default `data/slack_app.db`): OAuth installs (incl. bot tokens), via `slack_sdk` `SQLite3InstallationStore`.
- **`OAUTH_STATE_DIR`**: short-lived OAuth `state` files (CSRF).

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
