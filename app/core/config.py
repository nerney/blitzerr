import logging
import os
from dataclasses import dataclass, field, fields
from pathlib import Path

import yaml

CONFIG_DIR = Path(os.environ.get("BLITZERR_CONFIG_DIR", "/config"))
CONFIG_FILE = CONFIG_DIR / "config.yaml"
DB_PATH = CONFIG_DIR / "blitzerr.db"
NFLVERSE_REFRESH_HOURS = 12

logger = logging.getLogger(__name__)

_REDACTED = {"api_key", "password"}


# ── Section dataclasses ───────────────────────────────────────────────

@dataclass
class ServerConfig:
    host: str = "::"
    port: int = 8012
    log_level: str = "info"


@dataclass
class LibraryConfig:
    root_path: str = "/data/media/blitzerr"


@dataclass
class ProwlarrConfig:
    url: str = "http://localhost:9696"
    api_key: str = ""


@dataclass
class QBittorrentConfig:
    url: str = "http://localhost:8888"
    username: str = ""
    password: str = ""
    category: str = "blitzerr"


@dataclass
class SabnzbdConfig:
    url: str = "http://localhost:8080"
    api_key: str = ""
    category: str = "blitzerr"


@dataclass
class Settings:
    server: ServerConfig = field(default_factory=ServerConfig)
    library: LibraryConfig = field(default_factory=LibraryConfig)
    prowlarr: ProwlarrConfig = field(default_factory=ProwlarrConfig)
    qbittorrent: QBittorrentConfig = field(default_factory=QBittorrentConfig)
    sabnzbd: SabnzbdConfig = field(default_factory=SabnzbdConfig)


_SECTIONS: list[tuple[str, type]] = [
    ("server", ServerConfig),
    ("library", LibraryConfig),
    ("prowlarr", ProwlarrConfig),
    ("qbittorrent", QBittorrentConfig),
    ("sabnzbd", SabnzbdConfig),
]


# ── Config file helpers ───────────────────────────────────────────────

def _find_config_file() -> Path | None:
    for name in ("config.yaml", "config.yml"):
        p = CONFIG_DIR / name
        if p.exists():
            return p
    return None


def _serialize(s: Settings) -> str:
    """Produce a clean, comment-annotated YAML string from Settings."""
    sv = s.server
    li = s.library
    pr = s.prowlarr
    qb = s.qbittorrent
    sa = s.sabnzbd
    return (
        "# Blitzerr configuration\n"
        "# Updated on startup — missing fields are added automatically.\n"
        "\n"
        "server:\n"
        f'  host: "{sv.host}"  # "::" = IPv6 dual-stack (accepts IPv4 too)\n'
        f"  port: {sv.port}\n"
        f"  log_level: {sv.log_level}  # debug | info | warning | error\n"
        "\n"
        "library:\n"
        f"  root_path: {li.root_path}\n"
        "\n"
        "prowlarr:\n"
        f"  url: {pr.url}\n"
        f'  api_key: "{pr.api_key}"\n'
        "\n"
        "qbittorrent:\n"
        f"  url: {qb.url}\n"
        f'  username: "{qb.username}"\n'
        f'  password: "{qb.password}"\n'
        f"  category: {qb.category}\n"
        "\n"
        "sabnzbd:\n"
        f"  url: {sa.url}\n"
        f'  api_key: "{sa.api_key}"\n'
        f"  category: {sa.category}\n"
    )


def _write_config(s: Settings) -> None:
    """Atomically write config.yaml, preserving any existing .yml path."""
    target = _find_config_file() or CONFIG_FILE
    if target.suffix == ".yml":
        target = target.with_suffix(".yaml")
    tmp = target.with_suffix(".tmp")
    tmp.write_text(_serialize(s), encoding="utf-8")
    tmp.replace(target)


def _log_config(s: Settings) -> None:
    def fmt(obj) -> str:
        parts = []
        for f in fields(obj):
            val = "***" if f.name in _REDACTED else getattr(obj, f.name)
            parts.append(f"{f.name}={val}")
        return "  ".join(parts)

    for key, _ in _SECTIONS:
        logger.info("[config] %-12s %s", key + ":", fmt(getattr(s, key)))


# ── Main loader ───────────────────────────────────────────────────────

def load_settings() -> Settings:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    data: dict = {}
    config_file = _find_config_file()
    if config_file:
        try:
            with config_file.open() as f:
                data = yaml.safe_load(f) or {}
        except Exception as exc:
            logger.warning("Could not parse %s: %s", config_file, exc)

    s = Settings()
    for key, cls in _SECTIONS:
        section_data = data.get(key)
        if isinstance(section_data, dict):
            valid = {f.name for f in fields(cls)}
            setattr(s, key, cls(**{k: v for k, v in section_data.items() if k in valid}))

    _write_config(s)
    _log_config(s)
    return s


settings = load_settings()
