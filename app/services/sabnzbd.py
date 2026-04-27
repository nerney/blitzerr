import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.core.config import settings

logger = logging.getLogger(__name__)

SABNZBD_CHECK_INTERVAL_SECONDS = 60


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class NzbInfo:
    nzo_id: str
    name: str
    status: str
    progress: float
    size_mb: float
    category: str


@dataclass
class SabnzbdStatus:
    ok: bool
    checked_at: str | None = None
    message: str | None = None
    downloads: list[NzbInfo] = field(default_factory=list)


_status = SabnzbdStatus(ok=False, message="not yet checked")


def get_status() -> SabnzbdStatus:
    return _status


# ── Internal helpers ──────────────────────────────────────────────────

def _api_url(base_url: str, api_key: str, mode: str, **kwargs) -> str:
    params = {"mode": mode, "output": "json", "apikey": api_key, **kwargs}
    return base_url + "/api?" + urllib.parse.urlencode(params)


def _fetch_queue(base_url: str, api_key: str, category: str) -> list[NzbInfo]:
    url = _api_url(base_url, api_key, "queue", cat=category)
    with urllib.request.urlopen(url, timeout=10) as resp:
        data = json.loads(resp.read())
    slots = data.get("queue", {}).get("slots", [])
    return [
        NzbInfo(
            nzo_id=s.get("nzo_id", ""),
            name=s.get("filename", ""),
            status=s.get("status", ""),
            progress=float(s.get("percentage", 0)) / 100,
            size_mb=float(s.get("mb", 0)),
            category=s.get("cat", ""),
        )
        for s in slots
    ]


def _log_downloads(downloads: list[NzbInfo], category: str) -> None:
    lines = [f"[sabnzbd] {len(downloads)} download(s) in category '{category}':"]
    for d in downloads:
        pct = f"{d.progress * 100:.1f}%"
        lines.append(f"  • {d.name} — {d.status} {pct}")
    logger.info("\n".join(lines))


# ── Health check ──────────────────────────────────────────────────────

def check_health() -> SabnzbdStatus:
    global _status
    cfg = settings.sabnzbd
    base_url = cfg.url.rstrip("/")

    if not cfg.api_key:
        _status = SabnzbdStatus(ok=False, checked_at=_now_iso(), message="api_key not configured")
        logger.warning("SABnzbd health check skipped: api_key not configured")
        return _status

    try:
        url = _api_url(base_url, cfg.api_key, "version")
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
        if not data.get("version"):
            raise ValueError("unexpected response from /api?mode=version")

        downloads = _fetch_queue(base_url, cfg.api_key, cfg.category)
        _status = SabnzbdStatus(ok=True, checked_at=_now_iso(), downloads=downloads)
        _log_downloads(downloads, cfg.category)

    except urllib.error.HTTPError as exc:
        _status = SabnzbdStatus(ok=False, checked_at=_now_iso(), message=f"HTTP {exc.code}")
        logger.error("SABnzbd health check failed: HTTP %s", exc.code)
    except OSError as exc:
        _status = SabnzbdStatus(ok=False, checked_at=_now_iso(), message=str(exc))
        logger.error("SABnzbd health check failed: %s", exc)
    except ValueError as exc:
        _status = SabnzbdStatus(ok=False, checked_at=_now_iso(), message=str(exc))
        logger.error("SABnzbd health check failed: %s", exc)

    return _status
