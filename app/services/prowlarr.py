import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone

from app.core.config import settings
from app.db.connection import db_conn

logger = logging.getLogger(__name__)

PROWLARR_HEALTH_INTERVAL_HOURS = 4
USENET_CATEGORY = 5060


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class IndexerStatus:
    id: int
    name: str
    ok: bool
    checked_at: str | None = None
    disabled_till: str | None = None


@dataclass
class ProwlarrStatus:
    ok: bool
    checked_at: str | None = None
    message: str | None = None
    indexers: list[IndexerStatus] | None = None


_status = ProwlarrStatus(ok=False, message="not yet checked", indexers=[])


def get_status() -> ProwlarrStatus:
    return _status


# ── Internal helpers ──────────────────────────────────────────────────

def _fetch_json(path: str) -> list | dict:
    cfg = settings.prowlarr
    url = cfg.url.rstrip("/") + path
    req = urllib.request.Request(url, headers={"X-Api-Key": cfg.api_key})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def _has_category(categories: list, cat_id: int) -> bool:
    for cat in categories:
        if cat.get("id") == cat_id:
            return True
        if _has_category(cat.get("subCategories", []), cat_id):
            return True
    return False


# ── Indexer discovery ─────────────────────────────────────────────────

def fetch_usenet_indexers() -> list[dict]:
    """Return enabled Newznab/Usenet indexers that support category 5060 (TV/Sport)."""
    indexers = _fetch_json("/api/v1/indexer")
    return [
        idx for idx in indexers
        if idx.get("enable")
        and idx.get("protocol") == "usenet"
        and idx.get("implementationName", "").lower() == "newznab"
        and _has_category(idx.get("capabilities", {}).get("categories", []), USENET_CATEGORY)
    ]


def _upsert_indexers(indexers: list[dict]) -> None:
    now = _now_iso()
    records = [
        (
            idx["id"],
            idx.get("name", ""),
            idx.get("protocol", ""),
            idx.get("implementationName", ""),
            1 if idx.get("enable") else 0,
            now,
        )
        for idx in indexers
    ]
    with db_conn() as conn:
        conn.executemany(
            """INSERT INTO prowlarr_indexers (id, name, protocol, implementation, enabled, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                   name=excluded.name, protocol=excluded.protocol,
                   implementation=excluded.implementation, enabled=excluded.enabled,
                   updated_at=excluded.updated_at""",
            records,
        )


def _upsert_indexer_statuses(indexers: list[dict], failure_map: dict[int, dict]) -> list[IndexerStatus]:
    now = _now_iso()
    results = []
    records = []
    for idx in indexers:
        idx_id = idx["id"]
        failure = failure_map.get(idx_id)
        ok = failure is None
        disabled_till = failure.get("disabledTill") if failure else None
        records.append((idx_id, 1 if ok else 0, now,
                        failure.get("initialFailure") if failure else None,
                        failure.get("mostRecentFailure") if failure else None,
                        disabled_till))
        results.append(IndexerStatus(
            id=idx_id,
            name=idx.get("name", ""),
            ok=ok,
            checked_at=now,
            disabled_till=disabled_till,
        ))

    with db_conn() as conn:
        conn.executemany(
            """INSERT INTO prowlarr_indexer_status
                   (indexer_id, ok, checked_at, initial_failure, most_recent_failure, disabled_till)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(indexer_id) DO UPDATE SET
                   ok=excluded.ok, checked_at=excluded.checked_at,
                   initial_failure=excluded.initial_failure,
                   most_recent_failure=excluded.most_recent_failure,
                   disabled_till=excluded.disabled_till""",
            records,
        )
    return results


def get_indexer_statuses() -> list[IndexerStatus]:
    with db_conn() as conn:
        rows = conn.execute(
            """SELECT i.id, i.name, s.ok, s.checked_at, s.disabled_till
               FROM prowlarr_indexers i
               LEFT JOIN prowlarr_indexer_status s ON s.indexer_id = i.id
               WHERE i.enabled = 1
               ORDER BY i.name""",
        ).fetchall()
    return [
        IndexerStatus(
            id=row["id"],
            name=row["name"],
            ok=bool(row["ok"]) if row["ok"] is not None else False,
            checked_at=row["checked_at"],
            disabled_till=row["disabled_till"],
        )
        for row in rows
    ]


def _sync_indexers() -> list[IndexerStatus]:
    indexers = fetch_usenet_indexers()
    if not indexers:
        logger.info("[prowlarr] no enabled Newznab/usenet indexers found for category %d", USENET_CATEGORY)
        return []

    _upsert_indexers(indexers)

    try:
        statuses = _fetch_json("/api/v1/indexerstatus")
        failure_map = {s["indexerId"]: s for s in statuses}
    except Exception as exc:
        logger.warning("[prowlarr] could not fetch indexer statuses: %s", exc)
        failure_map = {}

    indexer_statuses = _upsert_indexer_statuses(indexers, failure_map)

    logger.info("[prowlarr] Newznab/usenet indexers supporting category %d:", USENET_CATEGORY)
    for s in indexer_statuses:
        health = "ok" if s.ok else f"degraded (disabled_till={s.disabled_till})"
        logger.info("[prowlarr]   • %s (id=%d) — %s", s.name, s.id, health)

    return indexer_statuses


# ── Health check ──────────────────────────────────────────────────────

def check_health() -> ProwlarrStatus:
    global _status
    cfg = settings.prowlarr

    if not cfg.api_key:
        _status = ProwlarrStatus(ok=False, checked_at=_now_iso(),
                                 message="api_key not configured", indexers=[])
        logger.warning("Prowlarr health check skipped: api_key not configured")
        return _status

    url = cfg.url.rstrip("/") + "/api/v1/health"
    req = urllib.request.Request(url, headers={"X-Api-Key": cfg.api_key})

    ok = False
    message = None
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            issues = json.loads(resp.read())
            errors = [i.get("message", "") for i in issues if i.get("type") == "error"]
            warnings = [i.get("message", "") for i in issues if i.get("type") == "warning"]
            ok = len(errors) == 0
            parts = [f"error: {m}" for m in errors] + [f"warning: {m}" for m in warnings]
            message = "; ".join(parts) if parts else None
    except urllib.error.HTTPError as exc:
        message = f"HTTP {exc.code}"
        logger.error("Prowlarr health check failed: HTTP %s", exc.code)
    except OSError as exc:
        message = str(exc)
        logger.error("Prowlarr health check failed: %s", exc)

    indexers: list[IndexerStatus] = []
    if ok:
        logger.info("Prowlarr healthy")
        try:
            indexers = _sync_indexers()
        except Exception as exc:
            logger.warning("Could not sync Prowlarr indexers: %s", exc)
    else:
        logger.warning("Prowlarr unhealthy: %s", message)

    _status = ProwlarrStatus(ok=ok, checked_at=_now_iso(), message=message, indexers=indexers)
    return _status
