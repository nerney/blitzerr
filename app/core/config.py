import os
import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml

CONFIG_DIR = Path(os.environ.get("BLITZERR_CONFIG_DIR", "/opt/blitzerr"))
CONFIG_FILE = CONFIG_DIR / "config.yaml"
DB_PATH = CONFIG_DIR / "blitzerr.db"

logger = logging.getLogger(__name__)


@dataclass
class Settings:
    host: str = "0.0.0.0"
    port: int = 8012
    log_level: str = "info"
    nflverse_refresh_interval_hours: int = 12
    db_path: Path = field(default_factory=lambda: DB_PATH)


def load_settings() -> Settings:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    data: dict = {}
    if CONFIG_FILE.exists():
        try:
            with CONFIG_FILE.open() as f:
                data = yaml.safe_load(f) or {}
        except Exception as exc:
            logger.warning("Could not parse config file %s: %s", CONFIG_FILE, exc)

    # Environment variables override YAML (BLITZERR_PORT, BLITZERR_LOG_LEVEL, etc.)
    env_map = {
        "BLITZERR_HOST": ("host", str),
        "BLITZERR_PORT": ("port", int),
        "BLITZERR_LOG_LEVEL": ("log_level", str),
        "BLITZERR_NFLVERSE_REFRESH_INTERVAL_HOURS": ("nflverse_refresh_interval_hours", int),
        "BLITZERR_DB_PATH": ("db_path", Path),
    }
    for env_key, (attr, cast) in env_map.items():
        val = os.environ.get(env_key)
        if val is not None:
            data[attr] = cast(val)

    s = Settings()
    for attr in ("host", "port", "log_level", "nflverse_refresh_interval_hours", "db_path"):
        if attr in data:
            setattr(s, attr, data[attr])

    return s


settings = load_settings()
