import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone

from app.core.config import settings

logger = logging.getLogger(__name__)

PROWLARR_HEALTH_INTERVAL_HOURS = 4
USENET_CATEGORY = 5060


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ProwlarrStatus:
    ok: bool
    checked_at: str | None = None
    message: str | None = None


_status = ProwlarrStatus(ok=False, message="not yet checked")


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


def _log_indexers(indexers: list[dict]) -> None:
    if not indexers:
        logger.info("[prowlarr] no enabled Newznab/usenet indexers found for category %d", USENET_CATEGORY)
        return
    logger.info("[prowlarr] Newznab/usenet indexers supporting category %d:", USENET_CATEGORY)
    for idx in indexers:
        logger.info("[prowlarr]   • %s (id=%s)", idx.get("name"), idx.get("id"))


# ── Health check ──────────────────────────────────────────────────────

def check_health() -> ProwlarrStatus:
    global _status
    cfg = settings.prowlarr

    if not cfg.api_key:
        _status = ProwlarrStatus(ok=False, checked_at=_now_iso(), message="api_key not configured")
        logger.warning("Prowlarr health check skipped: api_key not configured")
        return _status

    url = cfg.url.rstrip("/") + "/api/v1/health"
    req = urllib.request.Request(url, headers={"X-Api-Key": cfg.api_key})

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            issues = json.loads(resp.read())
            errors = [i.get("message", "") for i in issues if i.get("type") == "error"]
            warnings = [i.get("message", "") for i in issues if i.get("type") == "warning"]
            ok = len(errors) == 0
            parts = [f"error: {m}" for m in errors] + [f"warning: {m}" for m in warnings]
            _status = ProwlarrStatus(
                ok=ok,
                checked_at=_now_iso(),
                message="; ".join(parts) if parts else None,
            )
    except urllib.error.HTTPError as exc:
        _status = ProwlarrStatus(ok=False, checked_at=_now_iso(), message=f"HTTP {exc.code}")
        logger.error("Prowlarr health check failed: HTTP %s", exc.code)
    except OSError as exc:
        _status = ProwlarrStatus(ok=False, checked_at=_now_iso(), message=str(exc))
        logger.error("Prowlarr health check failed: %s", exc)

    if _status.ok:
        logger.info("Prowlarr healthy")
        try:
            _log_indexers(fetch_usenet_indexers())
        except Exception as exc:
            logger.warning("Could not fetch Prowlarr indexers: %s", exc)
    else:
        logger.warning("Prowlarr unhealthy: %s", _status.message)

    return _status
