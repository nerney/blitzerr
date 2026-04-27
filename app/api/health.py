import time
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.db.connection import check_db_connectivity
from app.services.nflverse_sync import get_last_sync_info
from app.services.prowlarr import get_status as prowlarr_status, get_indexer_statuses
from app.services.qbittorrent import get_status as qbittorrent_status

router = APIRouter(prefix="/api", tags=["health"])

_START_TIME = time.monotonic()
VERSION = "0.1.0"


class SyncStatus(BaseModel):
    dataset: str
    last_sync_at: Optional[str]
    status: Optional[str]
    rows_upserted: Optional[int]


class IndexerStatus(BaseModel):
    id: int
    name: str
    ok: bool
    checked_at: Optional[str]
    disabled_till: Optional[str]


class ServiceStatus(BaseModel):
    ok: bool
    checked_at: Optional[str]
    message: Optional[str]
    indexers: list[IndexerStatus] = []


class TorrentInfo(BaseModel):
    hash: str
    name: str
    state: str
    progress: float
    size: int
    category: str


class QBittorrentServiceStatus(BaseModel):
    ok: bool
    checked_at: Optional[str]
    message: Optional[str]
    downloads: list[TorrentInfo] = []


class HealthResponse(BaseModel):
    status: str
    version: str
    db_connected: bool
    nflverse_sync: list[SyncStatus]
    prowlarr: ServiceStatus
    qbittorrent: QBittorrentServiceStatus
    uptime_seconds: float


@router.get("/health", response_model=HealthResponse)
async def health():
    db_connected = check_db_connectivity()

    sync_statuses = []
    for dataset in ("teams", "games"):
        info = get_last_sync_info(dataset)
        if info:
            sync_statuses.append(SyncStatus(
                dataset=info["dataset"],
                last_sync_at=info.get("finished_at"),
                status=info.get("status"),
                rows_upserted=info.get("rows_upserted"),
            ))
        else:
            sync_statuses.append(SyncStatus(
                dataset=dataset,
                last_sync_at=None,
                status=None,
                rows_upserted=None,
            ))

    ps = prowlarr_status()
    try:
        db_indexers = get_indexer_statuses()
    except Exception:
        db_indexers = []
    indexers = [
        IndexerStatus(id=i.id, name=i.name, ok=i.ok,
                      checked_at=i.checked_at, disabled_till=i.disabled_till)
        for i in (ps.indexers or db_indexers)
    ]

    qs = qbittorrent_status()
    downloads = [
        TorrentInfo(hash=d.hash, name=d.name, state=d.state,
                    progress=d.progress, size=d.size, category=d.category)
        for d in qs.downloads
    ]

    overall_ok = db_connected and ps.ok and qs.ok
    return HealthResponse(
        status="ok" if overall_ok else "degraded",
        version=VERSION,
        db_connected=db_connected,
        nflverse_sync=sync_statuses,
        prowlarr=ServiceStatus(
            ok=ps.ok,
            checked_at=ps.checked_at,
            message=ps.message,
            indexers=indexers,
        ),
        qbittorrent=QBittorrentServiceStatus(
            ok=qs.ok,
            checked_at=qs.checked_at,
            message=qs.message,
            downloads=downloads,
        ),
        uptime_seconds=round(time.monotonic() - _START_TIME, 2),
    )
