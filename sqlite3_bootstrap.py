"""
Ensure `import sqlite3` works when CPython was built without `_sqlite3` (common for
hand-built /usr/local Python). slack-bolt loads OAuth modules that import sqlite3 at
import time, even if you use FileInstallationStore.

If stdlib sqlite3 fails, register `pysqlite3` as `sqlite3` (pip: pysqlite3-binary).
"""

from __future__ import annotations

import sys


def ensure_sqlite3() -> None:
    try:
        import sqlite3  # noqa: F401
        return
    except ModuleNotFoundError as e:
        err = str(e)
        if "_sqlite3" not in err and "No module named '_sqlite3'" not in err:
            raise
    for key in list(sys.modules.keys()):
        if key == "sqlite3" or key.startswith("sqlite3."):
            del sys.modules[key]
    try:
        import pysqlite3 as _sqlite  # type: ignore[import-not-found]
    except ImportError as ie:
        raise ModuleNotFoundError(
            "CPython has no _sqlite3. On the server: pip install pysqlite3-binary "
            "(or rebuild Python with sqlite-devel)."
        ) from ie
    sys.modules["sqlite3"] = _sqlite
