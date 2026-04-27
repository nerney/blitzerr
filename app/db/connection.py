import sqlite3
import logging
from contextlib import contextmanager
from pathlib import Path

from app.core.config import DB_PATH

logger = logging.getLogger(__name__)


def _get_db_path() -> Path:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return DB_PATH


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_get_db_path()), check_same_thread=False, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def db_conn():
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


def check_db_connectivity() -> bool:
    try:
        with db_conn() as conn:
            conn.execute("SELECT 1")
        return True
    except Exception as exc:
        logger.error("DB connectivity check failed: %s", exc)
        return False
