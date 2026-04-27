# Blitzerr

A Radarr/Sonarr-style NFL game media collection manager. Automatically finds, downloads, and organizes NFL game recordings into a Plex/Emby/Jellyfin-compatible library structure — with full NFO metadata, multi-team hardlink support, and Prowlarr-based search.

> **Status:** Early development — Milestone 1 (foundation) complete.

---

## Features

- **NFLverse data** — schedules, teams, and game results synced from official datasets, refreshed automatically every 12 hours
- **Arr-style library** — organizes games by team in a TV show layout (`Regular Season / Season YYYY`, `Postseason`, `Superbowls`) compatible with Plex, Emby, and Jellyfin
- **NFO metadata** — sidecar files written for every game
- **Multi-team support** — a single game file is hardlinked into every relevant team's library (no duplication)
- **Prowlarr search** — all indexer searching goes through Prowlarr (Usenet + torrent, TV/Sport category)
- **Sabnzbd + qBittorrent** — download client support
- **Hotio-compatible container** — PUID/PGID/UMASK support, `/config` volume, s6-overlay supervision

---

## Getting Started

### Docker (recommended)

```yaml
services:
  blitzerr:
    image: ghcr.io/nerney/blitzerr:latest
    container_name: blitzerr
    environment:
      - PUID=1000
      - PGID=1000
      - UMASK=002
      - TZ=America/New_York
    volumes:
      - /your/config:/config
      - /your/media/nfl:/media/nfl
    ports:
      - 8012:8012
    restart: unless-stopped
```

The web UI is available at `http://localhost:8012` after first run.

### Configuration

On first run, Blitzerr creates `/config/config.yaml` with defaults. Edit it to point to your download clients and library root:

```yaml
library:
  root_path: /media/nfl

prowlarr:
  url: http://prowlarr:9696
  api_key: ""

sabnzbd:
  url: http://sabnzbd:8080
  api_key: ""

qbittorrent:
  url: http://qbittorrent:8080
  username: ""
  password: ""
```

Settings can also be overridden with environment variables prefixed `BLITZERR_` (e.g. `BLITZERR_PORT=8012`).

### API

Interactive API docs are served at `http://localhost:8012/api/docs`.  
OpenAPI spec: `http://localhost:8012/openapi.json`

---

## Library Structure

```
{root}/
└── {Team Name}/
    ├── Regular Season/
    │   └── Season {YYYY}/
    ├── Postseason/
    │   └── Season {YYYY}/
    └── Superbowls/
        └── Season {YYYY}/
```

Episode numbers follow NFL week numbers. Games involving multiple followed teams are hardlinked — one file, multiple library entries.

---

## Milestones

| # | Name | Status |
|---|------|--------|
| M1 | Foundation — scaffolding, SQLite schema, NFLverse sync, FastAPI skeleton, health endpoint | ✅ Done |
| M2 | Library Management — folder structure, file naming, NFO generation, hardlink management | 🔲 Next |
| M3 | Search & Download — Prowlarr, Sabnzbd, qBittorrent integration, download tracking | 🔲 Planned |
| M4 | Import Pipeline — match download to game, rename, hardlink into library, mark collected | 🔲 Planned |
| M5 | Frontend — full Svelte UI for all backend features, first-run setup wizard | 🔲 Planned |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3, FastAPI, SQLite, APScheduler |
| Frontend | Svelte 5, TypeScript, SvelteKit |
| Container | hotio/base (Alpine), s6-overlay, PUID/PGID |
| Data | NFLverse (schedules, teams, results) |

---

## Development

```bash
# Backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

The Vite dev server proxies `/api` to `localhost:8012`, so the frontend talks to your local backend automatically.

---

## Related Repos

- [nerney/blitzerr-docker](https://github.com/nerney/blitzerr-docker) — Dockerfile and container build pipeline
