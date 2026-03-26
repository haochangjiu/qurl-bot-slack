"""Per-workspace LayerV API key storage (JSON file + Fernet)."""

import json
import logging
import os
import tempfile
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


def _path() -> Path:
    return Path(settings.workspace_layerv_keys_path)


def _load_all() -> dict[str, dict]:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.is_file():
        return {}
    try:
        raw = path.read_text(encoding="utf-8")
        if not raw.strip():
            return {}
        data = json.loads(raw)
        if not isinstance(data, dict):
            return {}
        return {str(k): v for k, v in data.items() if isinstance(v, dict)}
    except (json.JSONDecodeError, OSError) as e:
        logger.error("Failed to load workspace LayerV keys file %s: %s", path, e)
        return {}


def _atomic_write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=".layerv_keys_",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def init_workspace_key_store() -> None:
    """Ensure parent directory exists (file created on first set)."""
    _path().parent.mkdir(parents=True, exist_ok=True)


def get_api_key(team_id: str | None) -> str | None:
    """Return decrypted LayerV API key for workspace, or None."""
    if not team_id:
        return None
    with _lock:
        data = _load_all()
    row = data.get(team_id)
    if not row:
        return None
    enc = row.get("api_key_encrypted")
    if not enc:
        return None
    try:
        return _fernet().decrypt(str(enc).encode()).decode()
    except Exception as e:
        logger.error(f"Failed to decrypt LayerV key for team {team_id}: {e}")
        return None


def set_api_key(team_id: str, api_key: str) -> None:
    enc = _fernet().encrypt(api_key.encode()).decode()
    prefix = api_key[:8] + "..." if len(api_key) > 8 else api_key
    now = datetime.now(timezone.utc).isoformat()
    with _lock:
        data = _load_all()
        data[team_id] = {
            "api_key_encrypted": enc,
            "api_key_prefix": prefix,
            "updated_at": now,
        }
        _atomic_write(_path(), data)
    logger.info(f"Stored LayerV API key for workspace {team_id}")


def delete_api_key(team_id: str) -> bool:
    with _lock:
        data = _load_all()
        if team_id not in data:
            return False
        del data[team_id]
        _atomic_write(_path(), data)
        return True


def get_key_info(team_id: str | None) -> dict | None:
    """Prefix and updated_at for /mykey (no full key)."""
    if not team_id:
        return None
    with _lock:
        data = _load_all()
    row = data.get(team_id)
    if not row:
        return None
    return {
        "api_key_prefix": row.get("api_key_prefix"),
        "updated_at": row.get("updated_at"),
    }
