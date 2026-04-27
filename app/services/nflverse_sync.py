import csv
import io
import logging
import urllib.request
from datetime import datetime, timezone

from app.core.config import settings, NFLVERSE_REFRESH_HOURS
from app.db.connection import db_conn

logger = logging.getLogger(__name__)

GAMES_URL = "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv"
TEAMS_URL = "https://github.com/nflverse/nflverse-data/releases/download/teams/teams_colors_logos.csv"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_int(val: str | None) -> int | None:
    if val is None or val.strip() == "" or val.strip().upper() == "NA":
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def _to_float(val: str | None) -> float | None:
    if val is None or val.strip() == "" or val.strip().upper() == "NA":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _to_str(val: str | None) -> str | None:
    if val is None or val.strip() == "" or val.strip().upper() == "NA":
        return None
    return val.strip()


def fetch_csv(url: str) -> list[dict]:
    with urllib.request.urlopen(url, timeout=60) as resp:
        text = io.TextIOWrapper(resp, encoding="utf-8")
        return list(csv.DictReader(text))


def _start_sync_audit(conn, dataset: str) -> int:
    cur = conn.execute(
        "INSERT INTO nflverse_sync (dataset, started_at, status) VALUES (?, ?, 'running')",
        (dataset, _now_iso()),
    )
    return cur.lastrowid


def _finish_sync_audit(conn, row_id: int, rows_fetched: int, rows_upserted: int) -> None:
    conn.execute(
        """UPDATE nflverse_sync
           SET finished_at=?, status='success', rows_fetched=?, rows_upserted=?
           WHERE id=?""",
        (_now_iso(), rows_fetched, rows_upserted, row_id),
    )


def _fail_sync_audit(conn, row_id: int, error: str) -> None:
    conn.execute(
        "UPDATE nflverse_sync SET finished_at=?, status='error', error_message=? WHERE id=?",
        (_now_iso(), error, row_id),
    )


def is_sync_stale(dataset: str) -> bool:
    with db_conn() as conn:
        row = conn.execute(
            """SELECT finished_at FROM nflverse_sync
               WHERE dataset=? AND status='success'
               ORDER BY started_at DESC LIMIT 1""",
            (dataset,),
        ).fetchone()

    if row is None or row["finished_at"] is None:
        return True

    last = datetime.fromisoformat(row["finished_at"])
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    age_hours = (datetime.now(timezone.utc) - last).total_seconds() / 3600
    return age_hours >= NFLVERSE_REFRESH_HOURS


def get_last_sync_info(dataset: str) -> dict | None:
    with db_conn() as conn:
        row = conn.execute(
            """SELECT dataset, finished_at, status, rows_upserted
               FROM nflverse_sync
               WHERE dataset=?
               ORDER BY started_at DESC LIMIT 1""",
            (dataset,),
        ).fetchone()
    return dict(row) if row else None


def sync_teams() -> dict:
    logger.info("Syncing teams from NFLverse")
    with db_conn() as conn:
        audit_id = _start_sync_audit(conn, "teams")

    try:
        rows = fetch_csv(TEAMS_URL)
        now = _now_iso()
        records = [
            (
                _to_str(r.get("team_abbr")),
                _to_str(r.get("team_name")) or "",
                _to_str(r.get("team_id")),
                _to_str(r.get("team_nick")),
                _to_str(r.get("team_conf")),
                _to_str(r.get("team_division")),
                _to_str(r.get("team_color")),
                _to_str(r.get("team_color2")),
                _to_str(r.get("team_logo_espn")),
                _to_str(r.get("team_wordmark")),
                now,
            )
            for r in rows
            if _to_str(r.get("team_abbr"))
        ]

        with db_conn() as conn:
            conn.execute("BEGIN")
            conn.executemany(
                """INSERT INTO teams
                       (team_abbr, team_name, team_id, team_nick, team_conf, team_division,
                        team_color, team_color2, team_logo_espn, team_wordmark, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(team_abbr) DO UPDATE SET
                       team_name=excluded.team_name, team_id=excluded.team_id,
                       team_nick=excluded.team_nick, team_conf=excluded.team_conf,
                       team_division=excluded.team_division, team_color=excluded.team_color,
                       team_color2=excluded.team_color2, team_logo_espn=excluded.team_logo_espn,
                       team_wordmark=excluded.team_wordmark, updated_at=excluded.updated_at""",
                records,
            )
            conn.execute("COMMIT")
            audit_conn = conn

        with db_conn() as conn:
            _finish_sync_audit(conn, audit_id, len(rows), len(records))

        logger.info("Teams sync complete: %d upserted", len(records))
        return {"dataset": "teams", "rows_fetched": len(rows), "rows_upserted": len(records)}

    except Exception as exc:
        logger.error("Teams sync failed: %s", exc)
        with db_conn() as conn:
            _fail_sync_audit(conn, audit_id, str(exc))
        raise


def sync_games() -> dict:
    logger.info("Syncing games from NFLverse")
    with db_conn() as conn:
        audit_id = _start_sync_audit(conn, "games")

    try:
        rows = fetch_csv(GAMES_URL)
        now = _now_iso()
        records = [
            (
                _to_str(r.get("game_id")),
                _to_int(r.get("season")),
                _to_str(r.get("game_type")) or "",
                _to_int(r.get("week")),
                _to_str(r.get("gameday")),
                _to_str(r.get("weekday")),
                _to_str(r.get("gametime")),
                _to_str(r.get("away_team")) or "",
                _to_str(r.get("home_team")) or "",
                _to_int(r.get("away_score")),
                _to_int(r.get("home_score")),
                _to_str(r.get("location")),
                _to_float(r.get("result")),
                _to_float(r.get("total")),
                _to_int(r.get("overtime")),
                _to_str(r.get("old_game_id")),
                _to_str(r.get("gsis")),
                _to_str(r.get("nfl_detail_id")),
                _to_str(r.get("pfr")),
                _to_str(r.get("espn")),
                _to_int(r.get("away_rest")),
                _to_int(r.get("home_rest")),
                _to_float(r.get("away_moneyline")),
                _to_float(r.get("home_moneyline")),
                _to_float(r.get("spread_line")),
                _to_float(r.get("away_spread_odds")),
                _to_float(r.get("home_spread_odds")),
                _to_float(r.get("total_line")),
                _to_float(r.get("under_odds")),
                _to_float(r.get("over_odds")),
                _to_int(r.get("div_game")),
                _to_str(r.get("roof")),
                _to_str(r.get("surface")),
                _to_float(r.get("temp")),
                _to_float(r.get("wind")),
                _to_str(r.get("away_qb_id")),
                _to_str(r.get("home_qb_id")),
                _to_str(r.get("away_qb_name")),
                _to_str(r.get("home_qb_name")),
                _to_str(r.get("away_coach")),
                _to_str(r.get("home_coach")),
                _to_str(r.get("referee")),
                _to_str(r.get("stadium_id")),
                _to_str(r.get("stadium")),
                now,
            )
            for r in rows
            if _to_str(r.get("game_id"))
        ]

        with db_conn() as conn:
            conn.execute("BEGIN")
            conn.executemany(
                """INSERT INTO games
                       (game_id, season, game_type, week, gameday, weekday, gametime,
                        away_team, home_team, away_score, home_score, location, result, total,
                        overtime, old_game_id, gsis, nfl_detail_id, pfr, espn,
                        away_rest, home_rest, away_moneyline, home_moneyline, spread_line,
                        away_spread_odds, home_spread_odds, total_line, under_odds, over_odds,
                        div_game, roof, surface, temp, wind,
                        away_qb_id, home_qb_id, away_qb_name, home_qb_name,
                        away_coach, home_coach, referee, stadium_id, stadium, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(game_id) DO UPDATE SET
                       season=excluded.season, game_type=excluded.game_type, week=excluded.week,
                       gameday=excluded.gameday, weekday=excluded.weekday, gametime=excluded.gametime,
                       away_team=excluded.away_team, home_team=excluded.home_team,
                       away_score=excluded.away_score, home_score=excluded.home_score,
                       location=excluded.location, result=excluded.result, total=excluded.total,
                       overtime=excluded.overtime, old_game_id=excluded.old_game_id,
                       gsis=excluded.gsis, nfl_detail_id=excluded.nfl_detail_id,
                       pfr=excluded.pfr, espn=excluded.espn,
                       away_rest=excluded.away_rest, home_rest=excluded.home_rest,
                       away_moneyline=excluded.away_moneyline, home_moneyline=excluded.home_moneyline,
                       spread_line=excluded.spread_line, away_spread_odds=excluded.away_spread_odds,
                       home_spread_odds=excluded.home_spread_odds, total_line=excluded.total_line,
                       under_odds=excluded.under_odds, over_odds=excluded.over_odds,
                       div_game=excluded.div_game, roof=excluded.roof, surface=excluded.surface,
                       temp=excluded.temp, wind=excluded.wind,
                       away_qb_id=excluded.away_qb_id, home_qb_id=excluded.home_qb_id,
                       away_qb_name=excluded.away_qb_name, home_qb_name=excluded.home_qb_name,
                       away_coach=excluded.away_coach, home_coach=excluded.home_coach,
                       referee=excluded.referee, stadium_id=excluded.stadium_id,
                       stadium=excluded.stadium, updated_at=excluded.updated_at""",
                records,
            )
            conn.execute("COMMIT")

        with db_conn() as conn:
            _finish_sync_audit(conn, audit_id, len(rows), len(records))

        logger.info("Games sync complete: %d upserted", len(records))
        return {"dataset": "games", "rows_fetched": len(rows), "rows_upserted": len(records)}

    except Exception as exc:
        logger.error("Games sync failed: %s", exc)
        with db_conn() as conn:
            _fail_sync_audit(conn, audit_id, str(exc))
        raise


def sync_all_if_stale() -> None:
    if is_sync_stale("teams"):
        sync_teams()
    else:
        logger.info("Teams data is fresh, skipping sync")

    if is_sync_stale("games"):
        sync_games()
    else:
        logger.info("Games data is fresh, skipping sync")


def sync_all_force() -> None:
    sync_teams()
    sync_games()
