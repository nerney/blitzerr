import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http.cookiejar import CookieJar

from app.core.config import settings

logger = logging.getLogger(__name__)

QBITTORRENT_CHECK_INTERVAL_SECONDS = 60


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class TorrentInfo:
    hash: str
    name: str
    state: str
    progress: float
    size: int
    category: str


@dataclass
class QBittorrentStatus:
    ok: bool
    checked_at: str | None = None
    message: str | None = None
    downloads: list[TorrentInfo] = field(default_factory=list)


_status = QBittorrentStatus(ok=False, message="not yet checked")


def get_status() -> QBittorrentStatus:
    return _status


# ── Internal helpers ──────────────────────────────────────────────────

def _make_opener() -> urllib.request.OpenerDirector:
    jar = CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def _login(opener: urllib.request.OpenerDirector, base_url: str, username: str, password: str) -> bool:
    data = urllib.parse.urlencode({"username": username, "password": password}).encode()
    req = urllib.request.Request(base_url + "/api/v2/auth/login", data=data, method="POST")
    with opener.open(req, timeout=10) as resp:
        return resp.read().decode().strip() == "Ok."


def _fetch_downloads(opener: urllib.request.OpenerDirector, base_url: str, category: str) -> list[TorrentInfo]:
    url = base_url + "/api/v2/torrents/info?" + urllib.parse.urlencode({"category": category})
    with opener.open(url, timeout=10) as resp:
        data = json.loads(resp.read())
    return [
        TorrentInfo(
            hash=t.get("hash", ""),
            name=t.get("name", ""),
            state=t.get("state", ""),
            progress=t.get("progress", 0.0),
            size=t.get("size", 0),
            category=t.get("category", ""),
        )
        for t in data
    ]


def _log_downloads(downloads: list[TorrentInfo], category: str) -> None:
    lines = [f"[qbittorrent] {len(downloads)} download(s) in category '{category}':"]
    for d in downloads:
        pct = f"{d.progress * 100:.1f}%"
        lines.append(f"  • {d.name} — {d.state} {pct}")
    logger.info("\n".join(lines))


# ── Health check ──────────────────────────────────────────────────────

def check_health() -> QBittorrentStatus:
    global _status
    cfg = settings.qbittorrent
    base_url = cfg.url.rstrip("/")

    if not cfg.username:
        _status = QBittorrentStatus(ok=False, checked_at=_now_iso(), message="username not configured")
        logger.warning("qBittorrent health check skipped: username not configured")
        return _status

    opener = _make_opener()
    try:
        if not _login(opener, base_url, cfg.username, cfg.password):
            _status = QBittorrentStatus(ok=False, checked_at=_now_iso(), message="login failed")
            logger.warning("qBittorrent login failed")
            return _status

        downloads = _fetch_downloads(opener, base_url, cfg.category)
        _status = QBittorrentStatus(ok=True, checked_at=_now_iso(), downloads=downloads)
        _log_downloads(downloads, cfg.category)

    except urllib.error.HTTPError as exc:
        _status = QBittorrentStatus(ok=False, checked_at=_now_iso(), message=f"HTTP {exc.code}")
        logger.error("qBittorrent health check failed: HTTP %s", exc.code)
    except OSError as exc:
        _status = QBittorrentStatus(ok=False, checked_at=_now_iso(), message=str(exc))
        logger.error("qBittorrent health check failed: %s", exc)

    return _status
