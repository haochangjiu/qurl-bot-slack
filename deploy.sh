#!/bin/bash
set -e

# qurl-bot-slack deployment (Slack only: OAuth + SQLite + Socket Mode + aiohttp OAuth routes)
# Usage: sudo bash deploy.sh   (run from the repository root)
#
# Skips apt / venv creation when the host already has a suitable environment.
# Systemd enable/start runs only after the full runtime layout (files, venv, deps, unit) is in place.

APP_DIR="/opt/qurl-bot-slack"
SERVICE_NAME="qurl-bot-slack"

echo "=== qurl-bot-slack deployment ==="

if [ "$EUID" -ne 0 ]; then
    echo "Run this script with sudo"
    exit 1
fi

# --- [1/7] System packages: install only if Python / venv support is missing ---
echo "[1/7] Checking system Python / venv..."
need_apt=false
if ! command -v python3 >/dev/null 2>&1; then
    need_apt=true
fi
if ! python3 -c "import venv" 2>/dev/null; then
    need_apt=true
fi

if [ "$need_apt" = true ]; then
    echo "  Installing python3, python3-venv, python3-pip via apt..."
    apt update -qq
    apt install -y python3 python3-venv python3-pip
else
    echo "  System already has python3 with venv support — skipping apt install."
fi

# --- [2/7] Application directory and files ---
echo "[2/7] Syncing application directory..."
mkdir -p "$APP_DIR"
cp -r . "$APP_DIR/" 2>/dev/null || true
cd "$APP_DIR"

mkdir -p "$APP_DIR/data"

# --- [3/7] Virtualenv and Python dependencies (create venv only if absent) ---
echo "[3/7] Python virtual environment and dependencies..."
if [ -f "$APP_DIR/venv/bin/activate" ] && [ -x "$APP_DIR/venv/bin/python" ]; then
    echo "  Existing venv at $APP_DIR/venv — skipping python3 -m venv"
else
    echo "  Creating venv..."
    python3 -m venv venv
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
Description=qurl-bot-slack (OAuth SQLite + Socket Mode)
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
echo "  - Persistent data: $APP_DIR/data (slack_app.db, oauth_state, etc.) — back up this directory"
echo ""
echo "Common commands:"
echo "  Status:  systemctl status $SERVICE_NAME"
echo "  Logs:    journalctl -u $SERVICE_NAME -f"
echo "  Restart: systemctl restart $SERVICE_NAME"
echo "  Stop:    systemctl stop $SERVICE_NAME"
echo ""

echo "[7/7] Service status:"
systemctl status "$SERVICE_NAME" --no-pager || true
