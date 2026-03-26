#!/bin/bash
set -e

# qurl-bot-slack deployment (Slack only: OAuth + SQLite + Socket Mode + aiohttp OAuth routes)
# Usage: sudo bash deploy.sh   (run from the repository root)
#
# Skips apt / venv creation when the host already has a suitable environment.
# Systemd enable/start runs only after the full runtime layout (files, venv, deps, unit) is in place.

APP_DIR="/opt/qurl-bot-slack"
SERVICE_NAME="qurl-bot-slack"

# Python 3.10+ required (httpx, pydantic v2, etc.). Prefer newer interpreters first.
python_min_310() {
    local c
    for c in /usr/bin/python3.12 /usr/bin/python3.11 /usr/bin/python3.10 \
        /usr/local/bin/python3.12 /usr/local/bin/python3.11 /usr/local/bin/python3.10 \
        /opt/rh/rh-python311/root/usr/bin/python3 /opt/rh/rh-python310/root/usr/bin/python3 \
        "$(command -v python3 2>/dev/null)" /usr/bin/python3; do
        [ -n "$c" ] && [ -x "$c" ] || continue
        if "$c" -c "import sys; sys.exit(0 if sys.version_info[:2]>=(3,10) else 1)" 2>/dev/null; then
            printf '%s\n' "$c"
            return 0
        fi
    done
    return 1
}

echo "=== qurl-bot-slack deployment ==="

if [ "$EUID" -ne 0 ]; then
    echo "Run this script with sudo"
    exit 1
fi

# --- [1/7] System packages: install only if Python / venv support is missing ---
echo "[1/7] Checking system Python / venv (need Python 3.10+)..."
need_pkg=false
if ! command -v python3 >/dev/null 2>&1; then
    need_pkg=true
fi
if ! python3 -c "import venv" 2>/dev/null; then
    need_pkg=true
fi

if command -v apt-get >/dev/null 2>&1; then
    apt update -qq
    if [ "$need_pkg" = true ]; then
        echo "  Installing python3, python3-venv, python3-pip, libsqlite3-dev via apt..."
        apt install -y python3 python3-venv python3-pip libsqlite3-dev
    else
        echo "  Ensuring libsqlite3-dev (needed if you ever build Python from source)..."
        apt install -y libsqlite3-dev
    fi
elif command -v dnf >/dev/null 2>&1; then
    if [ "$need_pkg" = true ]; then
        echo "  Installing python3, python3-pip, sqlite-devel via dnf..."
        dnf install -y python3 python3-pip sqlite-devel
    else
        echo "  Ensuring sqlite-devel..."
        dnf install -y sqlite-devel
    fi
elif command -v yum >/dev/null 2>&1; then
    if [ "$need_pkg" = true ]; then
        echo "  Installing python3, python3-pip, sqlite-devel via yum..."
        yum install -y python3 python3-pip sqlite-devel
    else
        echo "  Ensuring sqlite-devel..."
        yum install -y sqlite-devel
    fi
elif command -v microdnf >/dev/null 2>&1; then
    echo "  Installing python3, pip, sqlite-devel via microdnf..."
    microdnf install -y python3 python3-pip sqlite-devel
else
    echo "  No apt/dnf/yum/microdnf — install Python 3.10+ manually."
fi

if ! PYTHON_BIN="$(python_min_310)"; then
    echo ""
    echo "ERROR: Need Python 3.10+ (see README / requirements.txt)."
    echo "  CentOS 7 yum python3 is 3.6 — install rh-python311 (SCL), IUS python311, or build Python 3.10+ under /usr/local."
    exit 1
fi
echo "  Using Python for venv: $PYTHON_BIN ($("$PYTHON_BIN" --version 2>&1))"

# --- [2/7] Application directory and files ---
echo "[2/7] Syncing application directory..."
mkdir -p "$APP_DIR"
cp -r . "$APP_DIR/" 2>/dev/null || true
cd "$APP_DIR"

mkdir -p "$APP_DIR/data"

# --- [3/7] Virtualenv and Python dependencies (create venv only if absent) ---
echo "[3/7] Python virtual environment and dependencies..."
if [ -f "$APP_DIR/venv/bin/activate" ] && [ -x "$APP_DIR/venv/bin/python" ]; then
    if ! "$APP_DIR/venv/bin/python" -c "import sys; sys.exit(0 if sys.version_info[:2]>=(3,10) else 1)" 2>/dev/null; then
        echo "  Existing venv has Python <3.10 — removing venv..."
        rm -rf "$APP_DIR/venv"
    fi
fi
if [ -f "$APP_DIR/venv/bin/activate" ] && [ -x "$APP_DIR/venv/bin/python" ]; then
    echo "  Existing venv at $APP_DIR/venv — skipping venv creation"
else
    echo "  Creating venv with $PYTHON_BIN ..."
    "$PYTHON_BIN" -m venv venv
fi
# shellcheck source=/dev/null
source venv/bin/activate
echo "  Installing / updating packages from requirements.txt..."
pip install -q -r requirements.txt

# --- [4/7] Configuration file reminder ---
echo "[4/7] Checking configuration..."
if [ ! -f "$APP_DIR/.env" ]; then
    echo "  Warning: .env is missing. Create and edit it (OAuth, Socket Mode, Claude, LayerV, etc.):"
    echo "    cp $APP_DIR/.env.example $APP_DIR/.env"
    echo "    nano $APP_DIR/.env"
fi

# --- [5/7] systemd unit (no start yet) ---
echo "[5/7] Writing systemd unit..."
cat > "/etc/systemd/system/${SERVICE_NAME}.service" << EOF
[Unit]
Description=qurl-bot-slack (OAuth file store + Socket Mode)
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$APP_DIR
Environment=PATH=$APP_DIR/venv/bin
ExecStart=$APP_DIR/venv/bin/python app.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# --- [6/7] Enable and start service (after full runtime is deployed) ---
echo "[6/7] Enabling and starting service (runtime ready)..."
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"

echo ""
echo "=== Deployment finished ==="
echo ""
echo "Notes:"
echo "  - Entry point: app.py (OAuth HTTP on HTTP_HOST/HTTP_PORT, default 0.0.0.0:8080; events via Socket Mode)"
echo "  - In production, terminate TLS at Nginx/Caddy and proxy HTTPS to this host's HTTP_PORT; URL must match SLACK_REDIRECT_URI"
echo "  - Persistent data: $APP_DIR/data (slack_installations, workspace_layerv_keys.json, oauth_state, etc.) — back up this directory"
echo ""
echo "Common commands:"
echo "  Status:  systemctl status $SERVICE_NAME"
echo "  Logs:    journalctl -u $SERVICE_NAME -f"
echo "  Restart: systemctl restart $SERVICE_NAME"
echo "  Stop:    systemctl stop $SERVICE_NAME"
echo ""

echo "[7/7] Service status:"
systemctl status "$SERVICE_NAME" --no-pager || true
