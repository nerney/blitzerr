import logging
import logging.config
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from app.core.config import settings
from app.core.scheduler import start_scheduler, stop_scheduler
from app.db.schema import init_db
from app.api.router import api_router

_BANNER = r"""
        _.-=""=-._
      .'\\-++++-//'.
     (  ||      ||  )
      './/      \\.'
        `'-=..=-'`
"""


def _log_config(level: str) -> dict:
    lvl = level.upper()
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s %(levelname)-8s %(name)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            }
        },
        "handlers": {
            "stdout": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "formatter": "default",
            }
        },
        "root": {"level": lvl, "handlers": ["stdout"]},
        "loggers": {
            "uvicorn":        {"propagate": True, "level": lvl},
            "uvicorn.error":  {"propagate": True, "level": lvl},
            "uvicorn.access": {"propagate": True, "level": lvl},
        },
    }


# Configure logging before anything else imports the logging module
logging.config.dictConfig(_log_config(settings.server.log_level))


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="Blitzerr",
    description="NFL game media collection manager",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.include_router(api_router)

if __name__ == "__main__":
    print(_BANNER, flush=True)
    uvicorn.run(
        "main:app",
        host=settings.server.host,
        port=settings.server.port,
        log_config=_log_config(settings.server.log_level),
        server_header=False,
        reload=False,
    )
