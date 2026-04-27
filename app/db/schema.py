import logging
from app.db.connection import db_conn

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS teams (
    team_abbr       TEXT PRIMARY KEY,
    team_name       TEXT NOT NULL,
    team_id         TEXT,
    team_nick       TEXT,
    team_conf       TEXT,
    team_division   TEXT,
    team_color      TEXT,
    team_color2     TEXT,
    team_logo_espn  TEXT,
    team_wordmark   TEXT,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS games (
    game_id             TEXT PRIMARY KEY,
    season              INTEGER NOT NULL,
    game_type           TEXT NOT NULL,
    week                INTEGER NOT NULL,
    gameday             TEXT,
    weekday             TEXT,
    gametime            TEXT,
    away_team           TEXT NOT NULL REFERENCES teams(team_abbr),
    home_team           TEXT NOT NULL REFERENCES teams(team_abbr),
    away_score          INTEGER,
    home_score          INTEGER,
    location            TEXT,
    result              REAL,
    total               REAL,
    overtime            INTEGER,
    old_game_id         TEXT,
    gsis                TEXT,
    nfl_detail_id       TEXT,
    pfr                 TEXT,
    espn                TEXT,
    away_rest           INTEGER,
    home_rest           INTEGER,
    away_moneyline      REAL,
    home_moneyline      REAL,
    spread_line         REAL,
    away_spread_odds    REAL,
    home_spread_odds    REAL,
    total_line          REAL,
    under_odds          REAL,
    over_odds           REAL,
    div_game            INTEGER,
    roof                TEXT,
    surface             TEXT,
    temp                REAL,
    wind                REAL,
    away_qb_id          TEXT,
    home_qb_id          TEXT,
    away_qb_name        TEXT,
    home_qb_name        TEXT,
    away_coach          TEXT,
    home_coach          TEXT,
    referee             TEXT,
    stadium_id          TEXT,
    stadium             TEXT,
    updated_at          TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_games_season_week  ON games (season, week);
CREATE INDEX IF NOT EXISTS idx_games_gameday      ON games (gameday);
CREATE INDEX IF NOT EXISTS idx_games_away_team    ON games (away_team);
CREATE INDEX IF NOT EXISTS idx_games_home_team    ON games (home_team);

CREATE TABLE IF NOT EXISTS nflverse_sync (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset         TEXT NOT NULL,
    started_at      TEXT NOT NULL,
    finished_at     TEXT,
    status          TEXT NOT NULL,
    rows_fetched    INTEGER,
    rows_upserted   INTEGER,
    error_message   TEXT
);

CREATE INDEX IF NOT EXISTS idx_nflverse_sync_dataset_started
    ON nflverse_sync (dataset, started_at DESC);

CREATE TABLE IF NOT EXISTS prowlarr_indexers (
    id              INTEGER PRIMARY KEY,
    name            TEXT NOT NULL,
    protocol        TEXT NOT NULL,
    implementation  TEXT NOT NULL,
    enabled         INTEGER NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS prowlarr_indexer_status (
    indexer_id          INTEGER PRIMARY KEY REFERENCES prowlarr_indexers(id),
    ok                  INTEGER NOT NULL,
    checked_at          TEXT NOT NULL,
    initial_failure     TEXT,
    most_recent_failure TEXT,
    disabled_till       TEXT
);
"""


def init_db() -> None:
    logger.info("Initialising databasw")
    with db_conn() as conn:
        conn.executescript(SCHEMA_SQL)
    logger.info("Database ready")
