import time
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.db.connection import check_db_connectivity
from app.services.nflverse_sync import get_last_sync_info
from app.services.prowlarr import get_status as prowlarr_status, get_indexer_statuses

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


class HealthResponse(BaseModel):
    status: str
    version: str
    db_connected: bool
    nflverse_sync: list[SyncStatus]
    prowlarr: ServiceStatus
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

    if ps.indexers:
        indexers = [
            IndexerStatus(id=i.id, name=i.name, ok=i.ok,
                          checked_at=i.checked_at, disabled_till=i.disabled_till)
            for i in ps.indexers
        ]
    else:
        indexers = [
            IndexerStatus(id=i.id, name=i.name, ok=i.ok,
                          checked_at=i.checked_at, disabled_till=i.disabled_till)
            for i in db_indexers
        ]

    overall_ok = db_connected and ps.ok
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
        uptime_seconds=round(time.monotonic() - _START_TIME, 2),
    )
