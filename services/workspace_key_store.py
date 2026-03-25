"""Per-workspace LayerV API key storage (SQLite + Fernet)."""

import logging
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from cryptography.fernet import Fernet
from base64 import urlsafe_b64encode
from hashlib import sha256

from config import settings

logger = logging.getLogger(__name__)

_lock = threading.Lock()


def _fernet() -> Fernet:
    key = urlsafe_b64encode(sha256(settings.encryption_secret.encode()).digest())
    return Fernet(key)


def _connect() -> sqlite3.Connection:
    path = Path(settings.sqlite_database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_workspace_key_table() -> None:
    """Create table if missing (same DB file as Slack OAuth store)."""
    with _lock:
        with _connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS workspace_layerv_keys (
                    team_id TEXT PRIMARY KEY,
                    api_key_encrypted TEXT NOT NULL,
                    api_key_prefix TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            conn.commit()


def get_api_key(team_id: str | None) -> str | None:
    """Return decrypted LayerV API key for workspace, or None."""
    if not team_id:
        return None
    init_workspace_key_table()
    with _lock:
        with _connect() as conn:
            cur = conn.execute(
                "SELECT api_key_encrypted FROM workspace_layerv_keys WHERE team_id = ?",
                (team_id,),
            )
            row = cur.fetchone()
    if not row:
        return None
    try:
        return _fernet().decrypt(row[0].encode()).decode()
    except Exception as e:
        logger.error(f"Failed to decrypt LayerV key for team {team_id}: {e}")
        return None


def set_api_key(team_id: str, api_key: str) -> None:
    init_workspace_key_table()
    enc = _fernet().encrypt(api_key.encode()).decode()
    prefix = api_key[:8] + "..." if len(api_key) > 8 else api_key
    now = datetime.now(timezone.utc).isoformat()
    with _lock:
        with _connect() as conn:
            conn.execute(
                """
                INSERT INTO workspace_layerv_keys (team_id, api_key_encrypted, api_key_prefix, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(team_id) DO UPDATE SET
                    api_key_encrypted = excluded.api_key_encrypted,
                    api_key_prefix = excluded.api_key_prefix,
                    updated_at = excluded.updated_at;
                """,
                (team_id, enc, prefix, now),
            )
            conn.commit()
    logger.info(f"Stored LayerV API key for workspace {team_id}")


def delete_api_key(team_id: str) -> bool:
    init_workspace_key_table()
    with _lock:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM workspace_layerv_keys WHERE team_id = ?",
                (team_id,),
            )
            conn.commit()
            return cur.rowcount > 0


def get_key_info(team_id: str | None) -> dict | None:
    """Prefix and updated_at for /mykey (no full key)."""
    if not team_id:
        return None
    init_workspace_key_table()
    with _lock:
        with _connect() as conn:
            cur = conn.execute(
                "SELECT api_key_prefix, updated_at FROM workspace_layerv_keys WHERE team_id = ?",
                (team_id,),
            )
            row = cur.fetchone()
    if not row:
        return None
    return {"api_key_prefix": row[0], "updated_at": row[1]}
