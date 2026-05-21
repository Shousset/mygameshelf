"""
MyGameShelf — FastAPI REST Backend
Run with: uvicorn api.main:app --reload --port 8000
(from the mygameshelf/ directory)
"""

from __future__ import annotations
import os
import asyncio
import threading
from typing import Optional

import httpx
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Reuse existing DB logic
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from db.connection import initialize_schema, get_connection
from db.models import (
    add_game, list_games, get_game, update_game_status, rate_game, delete_game,
    log_session, get_sessions,
    add_to_wishlist, list_wishlist, remove_from_wishlist,
    get_stats,
    list_steam_games_with_appid, list_steam_games_missing_appid, set_game_external_id,
    set_game_sync_meta, set_game_metadata, set_game_last_played, get_game_local_stats,
    start_sync_run, finish_sync_run, get_last_sync_run,
)

app = FastAPI(title="MyGameShelf API", version="1.0.0")

# Allow calls from any Next.js port or local IP
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── SCHEDULER + SYNC LOCK ───────────────────────────────────────────────────

scheduler = BackgroundScheduler()
_sync_lock = threading.Lock()
_sync_in_progress = False


@app.on_event("startup")
def on_startup():
    try:
        initialize_schema()
        # LIVE PATCHES for older DBs predating these columns/tables
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("ALTER TABLE games ADD COLUMN IF NOT EXISTS external_id VARCHAR(100);")
                cur.execute("ALTER TABLE games ADD COLUMN IF NOT EXISTS last_synced_at TIMESTAMP;")
                cur.execute("ALTER TABLE games ADD COLUMN IF NOT EXISTS last_sync_status VARCHAR(60);")
                cur.execute("ALTER TABLE games ALTER COLUMN last_sync_status TYPE VARCHAR(60);")
                cur.execute("ALTER TABLE games ADD COLUMN IF NOT EXISTS last_played_at TIMESTAMP;")
                cur.execute("ALTER TABLE achievements ADD COLUMN IF NOT EXISTS icon_url VARCHAR(500);")
                cur.execute("ALTER TABLE achievements ADD COLUMN IF NOT EXISTS icon_gray_url VARCHAR(500);")
                cur.execute("ALTER TABLE achievements ADD COLUMN IF NOT EXISTS is_hidden BOOLEAN DEFAULT FALSE;")
                cur.execute("ALTER TABLE achievements ADD COLUMN IF NOT EXISTS global_pct NUMERIC(5,2);")
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS sync_runs (
                        id            SERIAL PRIMARY KEY,
                        started_at    TIMESTAMP DEFAULT NOW(),
                        finished_at   TIMESTAMP,
                        games_synced  INT DEFAULT 0,
                        errors        INT DEFAULT 0,
                        trigger       VARCHAR(20)
                    );
                    """
                )
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        print(f"[WARNING] Could not initialize schema: {e}")

    # Boot the background scheduler — runs Steam sync every 6h
    try:
        if not scheduler.running:
            scheduler.add_job(
                _scheduled_steam_sync,
                IntervalTrigger(hours=6),
                id="steam_sync",
                replace_existing=True,
            )
            scheduler.start()
            print("[scheduler] Started — Steam auto-sync every 6h")
    except Exception as e:
        print(f"[WARNING] Could not start scheduler: {e}")


@app.on_event("shutdown")
def on_shutdown():
    if scheduler.running:
        scheduler.shutdown(wait=False)


# ─── PYDANTIC MODELS ──────────────────────────────────────────────────────────

class GameCreate(BaseModel):
    title: str
    platform: str = ""
    genre: str = ""
    year: Optional[int] = None
    status: str = "Backlog"
    notes: str = ""

class StatusUpdate(BaseModel):
    status: str

class RatingUpdate(BaseModel):
    rating: float = Field(..., ge=0, le=10)
    notes: str = ""

class SessionCreate(BaseModel):
    hours: float = Field(..., gt=0)
    notes: str = ""

class WishlistCreate(BaseModel):
    title: str
    platform: str = ""
    priority: str = "Medium"
    notes: str = ""

class AchievementCreate(BaseModel):
    title: str
    description: str = ""

class AchievementToggle(BaseModel):
    is_unlocked: bool

class SteamImportRequest(BaseModel):
    steam_id: str
    api_key: str
    dry_run: bool = False

class BulkImport(BaseModel):
    titles: list[str]
    platform: str

# ─── HELPERS ──────────────────────────────────────────────────────────────────

def _row_to_game(row) -> dict:
    keys = ["id", "title", "platform", "genre", "year", "status", "rating", "hours_played", "external_id"]
    if row is None:
        return {}
    # list_games returns 9 cols; get_game returns all cols
    return dict(zip(keys, row[:9]))


# ─── GAMES ────────────────────────────────────────────────────────────────────

@app.get("/api/games")
def api_list_games(status: Optional[str] = None):
    rows = list_games(status)
    return [_row_to_game(r) for r in rows]


@app.post("/api/games", status_code=201)
def api_add_game(body: GameCreate):
    gid = add_game(body.title, body.platform, body.genre, body.year, body.status, body.notes)
    return {"id": gid}


@app.get("/api/games/{game_id}")
def api_get_game(game_id: int):
    row = get_game(game_id)
    if not row:
        raise HTTPException(status_code=404, detail="Game not found")
    return _row_to_game(row)


@app.put("/api/games/{game_id}/status")
def api_update_status(game_id: int, body: StatusUpdate):
    valid = ["Backlog", "Playing", "Completed", "Abandoned"]
    if body.status not in valid:
        raise HTTPException(status_code=400, detail=f"Status must be one of {valid}")
    update_game_status(game_id, body.status)
    return {"ok": True}


@app.put("/api/games/{game_id}/rating")
def api_rate_game(game_id: int, body: RatingUpdate):
    rate_game(game_id, body.rating, body.notes)
    return {"ok": True}


@app.delete("/api/games/{game_id}")
def api_delete_game(game_id: int):
    delete_game(game_id)
    return {"ok": True}


# ─── SESSIONS ─────────────────────────────────────────────────────────────────

@app.get("/api/games/{game_id}/sessions")
def api_get_sessions(game_id: int):
    rows = get_sessions(game_id)
    return [{"date": str(r[0]), "hours": float(r[1]), "notes": r[2]} for r in rows]


@app.post("/api/games/{game_id}/sessions", status_code=201)
def api_log_session(game_id: int, body: SessionCreate):
    if not get_game(game_id):
        raise HTTPException(status_code=404, detail="Game not found")
    log_session(game_id, body.hours, body.notes)
    return {"ok": True}


# ─── WISHLIST ─────────────────────────────────────────────────────────────────

@app.get("/api/wishlist")
def api_list_wishlist():
    rows = list_wishlist()
    keys = ["id", "title", "platform", "priority", "notes"]
    return [dict(zip(keys, r)) for r in rows]


@app.post("/api/wishlist", status_code=201)
def api_add_wishlist(body: WishlistCreate):
    add_to_wishlist(body.title, body.platform, body.priority, body.notes)
    return {"ok": True}


@app.delete("/api/wishlist/{wish_id}")
def api_remove_wishlist(wish_id: int):
    remove_from_wishlist(wish_id)
    return {"ok": True}


# ─── ACHIEVEMENTS ─────────────────────────────────────────────────────────────

from db.models import add_achievement, list_achievements, toggle_achievement, clear_game_achievements

@app.get("/api/games/{game_id}/achievements")
def api_list_achievements(game_id: int):
    rows = list_achievements(game_id)
    keys = ["id", "game_id", "title", "description", "is_unlocked", "unlocked_at",
            "icon_url", "icon_gray_url", "is_hidden", "global_pct"]
    out = []
    for r in rows:
        d = dict(zip(keys, r))
        d["unlocked_at"] = r[5].isoformat() if r[5] else None
        d["global_pct"] = float(r[9]) if r[9] is not None else None
        out.append(d)
    return out

@app.post("/api/games/{game_id}/achievements", status_code=201)
def api_add_achievement(game_id: int, body: AchievementCreate):
    if not get_game(game_id):
        raise HTTPException(status_code=404, detail="Game not found")
    ach_id = add_achievement(game_id, body.title, body.description)
    return {"id": ach_id}

@app.put("/api/achievements/{ach_id}/toggle")
def api_toggle_achievement(ach_id: int, body: AchievementToggle):
    toggle_achievement(ach_id, body.is_unlocked)
    return {"ok": True}

@app.post("/api/games/{game_id}/sync_steam")
async def api_sync_steam_achievements(game_id: int):
    game = get_game(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
        
    external_id = game[8]
    if not external_id:
        raise HTTPException(status_code=400, detail="Game has no Steam AppID attached. Maybe delete and re-import this game from Steam?")
        
    from dotenv import load_dotenv
    load_dotenv()
    
    api_key = os.getenv("STEAM_API_KEY")
    steam_id = os.getenv("STEAM_ID")
    if not api_key or not steam_id:
        raise HTTPException(status_code=400, detail="STEAM_API_KEY or STEAM_ID is missing from .env configuration.")
        
    # Triple Steam Queries — schema (achievement defs), player progress, and global rarity %
    schema_url = f"https://api.steampowered.com/ISteamUserStats/GetSchemaForGame/v2/?key={api_key}&appid={external_id}"
    player_url = f"https://api.steampowered.com/ISteamUserStats/GetPlayerAchievements/v0001/?appid={external_id}&key={api_key}&steamid={steam_id}"
    global_url = f"https://api.steampowered.com/ISteamUserStats/GetGlobalAchievementPercentagesForApp/v2/?gameid={external_id}&format=json"

    async with httpx.AsyncClient(timeout=15) as client:
        s_res, p_res, g_res = await asyncio.gather(
            client.get(schema_url), client.get(player_url), client.get(global_url),
        )

    if s_res.status_code != 200:
        raise HTTPException(status_code=502, detail="Steam API could not find achievement data for this game.")

    s_data = s_res.json()
    p_data = p_res.json() if p_res.status_code == 200 else {}
    g_data = g_res.json() if g_res.status_code == 200 else {}

    try:
        ach_schema = s_data["game"]["availableGameStats"]["achievements"]
    except KeyError:
        return {"success": True, "synced": 0, "message": "This game does not support Steam Achievements!"}

    player_achs = p_data.get("playerstats", {}).get("achievements", [])
    # apiname -> {achieved, unlocktime}
    player_map = {a["apiname"]: a for a in player_achs}

    # Global percentages keyed by apiname
    global_pct_map = {}
    for gp in (g_data.get("achievementpercentages") or {}).get("achievements", []):
        try:
            global_pct_map[gp["name"]] = float(gp["percent"])
        except (KeyError, TypeError, ValueError):
            pass

    # Wipe old and fresh sync
    clear_game_achievements(game_id)
    synced_count = 0

    from datetime import datetime
    for a in ach_schema:
        apiname = a.get("name")
        name = a.get("displayName", "Hidden Achievement")
        desc = a.get("description", "")
        pa = player_map.get(apiname) or {}
        unlocked = (pa.get("achieved") == 1)
        unlocktime = int(pa.get("unlocktime", 0) or 0)
        unlocked_at = datetime.fromtimestamp(unlocktime) if (unlocked and unlocktime > 0) else None
        add_achievement(
            game_id, name, desc, unlocked,
            icon_url=a.get("icon"),
            icon_gray_url=a.get("icongray"),
            is_hidden=bool(a.get("hidden")),
            unlocked_at=unlocked_at,
            global_pct=global_pct_map.get(apiname),
        )
        synced_count += 1
        
    return {"success": True, "synced": synced_count, "message": f"Successfully synced {synced_count} achievements from Steam!"}


# ─── STATS ────────────────────────────────────────────────────────────────────

@app.get("/api/stats")
def api_get_stats():
    return get_stats()


# ─── IMPORTS ──────────────────────────────────────────────────────────────────

STEAM_OWNED_URL = "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/"

@app.post("/api/import/steam")
async def api_import_steam(body: SteamImportRequest):
    params = {
        "key": body.api_key,
        "steamid": body.steam_id,
        "include_appinfo": "true",
        "include_played_free_games": "true",
        "format": "json",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(STEAM_OWNED_URL, params=params)

    if resp.status_code != 200:
        error_text = resp.text[:150].strip() if resp.text else "No extra details"
        raise HTTPException(status_code=502, detail=f"Steam API rejected your credentials (Error {resp.status_code}): {error_text}")

    data = resp.json()
    games_raw = data.get("response", {}).get("games", [])

    if not games_raw:
        return {"imported": 0, "games": [], "message": "No games found — check your SteamID and that your profile is public."}

    existing_titles = {r[1].lower() for r in list_games()}
    preview = []
    imported = 0

    for g in games_raw:
        name = g.get("name", "Unknown")
        appid = str(g.get("appid", ""))
        hours = round(g.get("playtime_forever", 0) / 60, 1)
        preview.append({"title": name, "hours_played": hours, "platform": "Steam", "skipped": name.lower() in existing_titles})

        if not body.dry_run and name.lower() not in existing_titles:
            gid = add_game(title=name, platform="Steam", genre="", year=None, status="Backlog", notes="", external_id=appid)
            if hours > 0:
                log_session(gid, hours, "Imported from Steam")
            imported += 1

    return {
        "imported": imported if not body.dry_run else 0,
        "games": preview,
        "message": f"Found {len(games_raw)} games on Steam. {'(Dry run — nothing saved)' if body.dry_run else f'Imported {imported} new games.'}",
    }


@app.post("/api/import/epic")
def api_import_epic(body: BulkImport):
    existing_titles = {r[1].lower() for r in list_games()}
    imported = 0
    skipped = []

    for title in body.titles:
        title = title.strip()
        if not title:
            continue
        if title.lower() in existing_titles:
            skipped.append(title)
            continue
        add_game(title=title, platform=body.platform, genre="", year=None, status="Backlog", notes="")
        imported += 1

    return {"imported": imported, "skipped": skipped}


@app.post("/api/import/psn")
def api_import_psn(body: BulkImport):
    existing_titles = {r[1].lower() for r in list_games()}
    imported = 0
    skipped = []

    for title in body.titles:
        title = title.strip()
        if not title:
            continue
        if title.lower() in existing_titles:
            skipped.append(title)
            continue
        add_game(title=title, platform=body.platform, genre="", year=None, status="Backlog", notes="")
        imported += 1

    return {"imported": imported, "skipped": skipped}


# ─── PER-GAME STATS + REFRESH ─────────────────────────────────────────────────

@app.get("/api/games/{game_id}/steam-stats")
def api_steam_stats(game_id: int):
    """Local stats panel for the per-game Sessions view. No Steam calls — uses the DB."""
    row = get_game_local_stats(game_id)
    if not row:
        raise HTTPException(status_code=404, detail="Game not found")
    hours_played, last_played_at, last_session_date, hours_2weeks, external_id, title, platform = row
    return {
        "game_id": game_id,
        "title": title,
        "platform": platform,
        "external_id": external_id,
        "total_hours": float(hours_played or 0),
        "hours_2weeks": float(hours_2weeks or 0),
        "last_played_at": last_played_at.isoformat() if last_played_at else None,
        "last_session_date": str(last_session_date) if last_session_date else None,
        "is_steam_linked": platform == "Steam" and bool(external_id),
    }


@app.post("/api/games/{game_id}/refresh")
def api_refresh_game(game_id: int):
    """Refresh one game from Steam: playtime delta, achievements, genre/year, last_played."""
    # Pull what we need with an explicit column list so column-order changes can't bite us.
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT title, platform, genre, year, hours_played, external_id FROM games WHERE id = %s;",
                (game_id,),
            )
            row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Game not found")
    title, platform, genre, year, hours_played, external_id = row

    if platform != "Steam":
        raise HTTPException(status_code=400, detail="This game is not linked to Steam.")
    if not external_id:
        raise HTTPException(status_code=400, detail="Game has no Steam AppID. Re-import it from Steam.")

    api_key = os.getenv("STEAM_API_KEY")
    steam_id = os.getenv("STEAM_ID")
    if not api_key or not steam_id:
        raise HTTPException(status_code=400, detail="STEAM_API_KEY / STEAM_ID missing from .env")

    with httpx.Client(timeout=30) as client:
        # Pull one row from GetOwnedGames so the existing sync helper can use its index format
        owned_index: dict[str, dict] = {}
        try:
            r = client.get(
                STEAM_OWNED_URL,
                params={
                    "key": api_key,
                    "steamid": steam_id,
                    "include_appinfo": "true",
                    "include_played_free_games": "true",
                    "appids_filter[0]": external_id,
                    "format": "json",
                },
            )
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Steam unreachable: {e}")

        if r.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Steam returned {r.status_code} for GetOwnedGames")

        for g in r.json().get("response", {}).get("games", []):
            owned_index[str(g.get("appid"))] = g

        if str(external_id) not in owned_index:
            # Steam returned the response but this game wasn't in it — likely Steam stripped it.
            # We still proceed so achievements can refresh, but playtime/last_played won't update.
            print(f"[refresh] appid {external_id} missing from GetOwnedGames response — skipping playtime/last_played update")

        try:
            _sync_one_steam_game(
                game_id, str(external_id), hours_played, genre, year,
                api_key, steam_id, owned_index, client,
            )
            _enrich_genre_year(game_id, str(external_id), genre, year, client)
            set_game_sync_meta(game_id, "ok")
        except httpx.TimeoutException:
            set_game_sync_meta(game_id, "timeout")
            raise HTTPException(status_code=504, detail="Steam timed out — try again in a moment.")
        except Exception as e:
            set_game_sync_meta(game_id, f"error: {type(e).__name__[:30]}"[:60])
            raise HTTPException(status_code=502, detail=f"Refresh failed: {e}")

    # Return the freshly-updated local stats so the UI can swap them in without a second round-trip
    return api_steam_stats(game_id)


@app.get("/api/dashboard/feed")
def api_dashboard_feed():
    """Returns: currently-playing (most recent rtime_last_played) + last 5 unlocks across the library."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, title, platform, external_id, hours_played, last_played_at
                FROM games
                WHERE last_played_at IS NOT NULL
                ORDER BY last_played_at DESC
                LIMIT 1;
                """
            )
            cp_row = cur.fetchone()

            currently_playing = None
            cp_recent = []
            if cp_row:
                cp_id, cp_title, cp_platform, cp_ext, cp_hours, cp_last = cp_row
                cur.execute(
                    """
                    SELECT title, icon_url, global_pct, unlocked_at
                    FROM achievements
                    WHERE game_id = %s AND is_unlocked = TRUE
                    ORDER BY unlocked_at DESC NULLS LAST
                    LIMIT 5;
                    """,
                    (cp_id,),
                )
                for r in cur.fetchall():
                    cp_recent.append({
                        "title": r[0],
                        "icon_url": r[1],
                        "global_pct": float(r[2]) if r[2] is not None else None,
                        "unlocked_at": r[3].isoformat() if r[3] else None,
                    })
                currently_playing = {
                    "id": cp_id,
                    "title": cp_title,
                    "platform": cp_platform,
                    "external_id": cp_ext,
                    "hours_played": float(cp_hours or 0),
                    "last_played_at": cp_last.isoformat() if cp_last else None,
                    "recent_unlocks_for_this_game": cp_recent,
                }

            cur.execute(
                """
                SELECT a.title, a.icon_url, a.global_pct, a.unlocked_at,
                       g.id, g.title, g.external_id
                FROM achievements a
                JOIN games g ON g.id = a.game_id
                WHERE a.is_unlocked = TRUE AND a.unlocked_at IS NOT NULL
                ORDER BY a.unlocked_at DESC
                LIMIT 8;
                """
            )
            recent_unlocks = [
                {
                    "title": r[0],
                    "icon_url": r[1],
                    "global_pct": float(r[2]) if r[2] is not None else None,
                    "unlocked_at": r[3].isoformat() if r[3] else None,
                    "game_id": r[4],
                    "game_title": r[5],
                    "game_external_id": r[6],
                }
                for r in cur.fetchall()
            ]
    finally:
        conn.close()

    return {"currently_playing": currently_playing, "recent_unlocks": recent_unlocks}


STEAM_PROFILE_URL = "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/"


@app.get("/api/steam/profile")
async def api_steam_profile():
    """Returns the configured Steam user's avatar, name, profile URL. Cached cheaply on the client side."""
    api_key = os.getenv("STEAM_API_KEY")
    steam_id = os.getenv("STEAM_ID")
    if not api_key or not steam_id:
        raise HTTPException(status_code=400, detail="STEAM_API_KEY / STEAM_ID missing from .env")

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.get(STEAM_PROFILE_URL, params={"key": api_key, "steamids": steam_id, "format": "json"})
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"Steam unreachable: {e}")

    if r.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Steam returned {r.status_code}")

    players = (r.json().get("response") or {}).get("players") or []
    if not players:
        raise HTTPException(status_code=404, detail="Steam profile not found")
    p = players[0]
    return {
        "steam_id": p.get("steamid"),
        "name": p.get("personaname"),
        "avatar": p.get("avatarmedium") or p.get("avatar"),
        "profile_url": p.get("profileurl"),
    }


# ─── STEAM RECENTLY PLAYED ────────────────────────────────────────────────────

STEAM_RECENT_URL = "https://api.steampowered.com/IPlayerService/GetRecentlyPlayedGames/v0001/"


@app.get("/api/steam/recently-played")
async def api_steam_recently_played():
    """Pull last-2-weeks playtime from Steam, joined to our local game rows by AppID."""
    api_key = os.getenv("STEAM_API_KEY")
    steam_id = os.getenv("STEAM_ID")
    if not api_key or not steam_id:
        raise HTTPException(status_code=400, detail="STEAM_API_KEY or STEAM_ID missing from .env")

    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.get(
                STEAM_RECENT_URL,
                params={"key": api_key, "steamid": steam_id, "format": "json"},
            )
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"Steam unreachable: {e}")

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Steam returned {resp.status_code}")

    games_raw = (resp.json().get("response") or {}).get("games") or []

    # Build appid -> local game lookup so the UI can link straight into the per-game session view
    local_by_appid = {}
    for r in list_steam_games_with_appid():
        gid, title, ext_id, *_ = r
        local_by_appid[str(ext_id)] = {"id": gid, "title": title}

    out = []
    for g in games_raw:
        appid = str(g.get("appid"))
        local = local_by_appid.get(appid)
        out.append({
            "appid": appid,
            "name": g.get("name"),
            "playtime_2weeks_hours": round((g.get("playtime_2weeks") or 0) / 60, 1),
            "playtime_forever_hours": round((g.get("playtime_forever") or 0) / 60, 1),
            "img_icon_url": g.get("img_icon_url"),
            "local_game_id": local["id"] if local else None,
            "local_title": local["title"] if local else None,
        })

    return {"games": out, "count": len(out)}


# ─── HEALTH + SYNC ────────────────────────────────────────────────────────────

@app.get("/api/health")
def api_health():
    """Cheap liveness probe used by the frontend to detect backend availability."""
    db_ok = True
    try:
        conn = get_connection()
        conn.close()
    except Exception:
        db_ok = False
    steam_configured = bool(os.getenv("STEAM_API_KEY") and os.getenv("STEAM_ID"))
    return {"ok": db_ok, "db": db_ok, "steam_configured": steam_configured}


STEAM_APPDETAILS_URL = "https://store.steampowered.com/api/appdetails"


def _fetch_steam_appdetails(appid: str, client) -> dict:
    """Hit the public Steam Store API. Returns the inner `data` dict or {} on failure."""
    try:
        r = client.get(STEAM_APPDETAILS_URL, params={"appids": appid, "l": "en"})
        if r.status_code != 200:
            return {}
        payload = r.json() or {}
        entry = payload.get(str(appid)) or {}
        if not entry.get("success"):
            return {}
        return entry.get("data") or {}
    except Exception:
        return {}


def _enrich_genre_year(game_id, appid, current_genre, current_year, client):
    """Look up genre + release year on the Steam Store if either is missing. Returns True if we made a network call."""
    needs_genre = not (current_genre and str(current_genre).strip())
    needs_year = current_year is None
    if not (needs_genre or needs_year):
        return False

    data = _fetch_steam_appdetails(appid, client)
    if not data:
        return True  # call was made even if we got nothing useful

    new_genre = None
    if needs_genre:
        genres = data.get("genres") or []
        names = [g.get("description") for g in genres if g.get("description")]
        if names:
            # Cap at 100 chars (schema limit)
            new_genre = ", ".join(names)[:100]

    new_year = None
    if needs_year:
        rd = (data.get("release_date") or {}).get("date") or ""
        # Steam returns strings like "12 Aug, 2015" or "2020" — pick the last 4-digit number
        import re
        m = re.search(r"\b(19|20)\d{2}\b", rd)
        if m:
            new_year = int(m.group(0))

    if new_genre or new_year:
        set_game_metadata(game_id, genre=new_genre, year=new_year)
    return True


def _sync_one_steam_game(game_id, appid, current_hours, current_genre, current_year, api_key, steam_id, owned_index, client):
    """Sync playtime + achievements + genre/year + last_played for a single Steam game. Raises on Steam errors."""
    from datetime import datetime
    # 1) Playtime — log delta vs current DB value so we don't double-count
    if appid in owned_index:
        info = owned_index[appid]
        steam_minutes = int(info.get("playtime_forever", 0) or 0)
        steam_hours = round(steam_minutes / 60, 1)
        current = float(current_hours or 0)
        delta = round(steam_hours - current, 1)
        if delta > 0.05:
            log_session(game_id, delta, "Auto-sync from Steam")
        # rtime_last_played is Unix seconds — 0 means never launched on Steam
        rtime = int(info.get("rtime_last_played", 0) or 0)
        if rtime > 0:
            try:
                set_game_last_played(game_id, datetime.fromtimestamp(rtime))
            except Exception as e:
                print(f"[sync] last_played write failed for {game_id}: {e}")

    # 2) Achievements — re-fetch schema + player progress + global rarity, then replace rows
    schema_url = f"https://api.steampowered.com/ISteamUserStats/GetSchemaForGame/v2/?key={api_key}&appid={appid}"
    player_url = f"https://api.steampowered.com/ISteamUserStats/GetPlayerAchievements/v0001/?appid={appid}&key={api_key}&steamid={steam_id}"
    global_url = f"https://api.steampowered.com/ISteamUserStats/GetGlobalAchievementPercentagesForApp/v2/?gameid={appid}&format=json"

    s_res = client.get(schema_url)
    if s_res.status_code != 200:
        return 0  # game has no public schema — not an error
    p_res = client.get(player_url)
    g_res = client.get(global_url)

    s_data = s_res.json()
    p_data = p_res.json() if p_res.status_code == 200 else {}
    g_data = g_res.json() if g_res.status_code == 200 else {}

    try:
        ach_schema = s_data["game"]["availableGameStats"]["achievements"]
    except KeyError:
        return 0

    player_achs = p_data.get("playerstats", {}).get("achievements", [])
    player_map = {a["apiname"]: a for a in player_achs}

    global_pct_map = {}
    for gp in (g_data.get("achievementpercentages") or {}).get("achievements", []):
        try:
            global_pct_map[gp["name"]] = float(gp["percent"])
        except (KeyError, TypeError, ValueError):
            pass

    clear_game_achievements(game_id)
    count = 0
    for a in ach_schema:
        apiname = a.get("name")
        name = a.get("displayName", "Hidden Achievement")
        desc = a.get("description", "")
        pa = player_map.get(apiname) or {}
        unlocked = (pa.get("achieved") == 1)
        unlocktime = int(pa.get("unlocktime", 0) or 0)
        unlocked_at = datetime.fromtimestamp(unlocktime) if (unlocked and unlocktime > 0) else None
        add_achievement(
            game_id, name, desc, unlocked,
            icon_url=a.get("icon"),
            icon_gray_url=a.get("icongray"),
            is_hidden=bool(a.get("hidden")),
            unlocked_at=unlocked_at,
            global_pct=global_pct_map.get(apiname),
        )
        count += 1
    return count


def _run_full_steam_sync(trigger: str) -> dict:
    """Full Steam sync over all games with an AppID. Sync-safe, callable from threadpool/scheduler."""
    api_key = os.getenv("STEAM_API_KEY")
    steam_id = os.getenv("STEAM_ID")
    if not api_key or not steam_id:
        return {"ok": False, "synced": 0, "errors": 0, "message": "STEAM_API_KEY / STEAM_ID missing from .env"}

    run_id = start_sync_run(trigger)
    synced = 0
    errors = 0
    backfilled = 0

    with httpx.Client(timeout=30) as client:
        # 1) One call to GetOwnedGames builds the playtime index for every game
        owned_index: dict[str, dict] = {}
        try:
            r = client.get(
                STEAM_OWNED_URL,
                params={
                    "key": api_key,
                    "steamid": steam_id,
                    "include_appinfo": "true",
                    "include_played_free_games": "true",
                    "format": "json",
                },
            )
            if r.status_code == 200:
                for g in r.json().get("response", {}).get("games", []):
                    owned_index[str(g.get("appid"))] = g
        except Exception as e:
            print(f"[sync] GetOwnedGames failed: {e}")
            # We can still try per-game achievement refresh, just no playtime updates.

        # 1b) Backfill missing external_ids by exact title match against the owned-games index.
        #     Games imported before the external_id column existed land here.
        if owned_index:
            by_title = {(g.get("name") or "").strip().lower(): str(g.get("appid"))
                        for g in owned_index.values() if g.get("appid")}
            for (gid, title) in list_steam_games_missing_appid():
                appid = by_title.get((title or "").strip().lower())
                if appid:
                    set_game_external_id(gid, appid)
                    backfilled += 1
            if backfilled:
                print(f"[sync] Backfilled external_id for {backfilled} game(s) by title match")

        # Now load the full set of syncable games (including the just-backfilled ones)
        games = list_steam_games_with_appid()
        if not games:
            finish_sync_run(run_id, 0, 0)
            return {"ok": True, "synced": 0, "errors": 0, "backfilled": backfilled, "message": "No Steam-linked games to sync."}

        import time
        for (gid, _title, appid, current_hours, current_genre, current_year) in games:
            try:
                _sync_one_steam_game(
                    gid, str(appid), current_hours, current_genre, current_year,
                    api_key, steam_id, owned_index, client,
                )
                # Genre/year enrichment via the rate-limited Store API
                hit_store = _enrich_genre_year(gid, str(appid), current_genre, current_year, client)
                set_game_sync_meta(gid, "ok")
                synced += 1
                if hit_store:
                    # Steam Store rate-limits ~200 req / 5 min — sleep ~1.5s between hits to stay safe
                    time.sleep(1.5)
            except Exception as e:
                # Map common faults to short tags so we stay well under the status column width,
                # and never let status-write failures abort the whole run.
                if isinstance(e, httpx.TimeoutException):
                    tag = "timeout"
                elif isinstance(e, httpx.HTTPError):
                    tag = "http_error"
                else:
                    tag = "error"
                detail = type(e).__name__[:30]
                try:
                    set_game_sync_meta(gid, f"{tag}: {detail}"[:60])
                except Exception as meta_e:
                    print(f"[sync] failed to record error for game {gid}: {meta_e}")
                errors += 1

    finish_sync_run(run_id, synced, errors)
    return {"ok": True, "synced": synced, "errors": errors, "backfilled": backfilled, "trigger": trigger}


def _scheduled_steam_sync():
    """APScheduler entrypoint — guarded so manual + scheduled runs don't overlap."""
    global _sync_in_progress
    with _sync_lock:
        if _sync_in_progress:
            print("[scheduler] Skip — sync already in progress")
            return
        _sync_in_progress = True
    try:
        result = _run_full_steam_sync("scheduler")
        print(f"[scheduler] {result}")
    finally:
        with _sync_lock:
            _sync_in_progress = False


@app.post("/api/sync/all")
def api_sync_all():
    """Manually trigger a full Steam sync. Returns when complete (FastAPI runs sync defs in a threadpool)."""
    global _sync_in_progress
    with _sync_lock:
        if _sync_in_progress:
            raise HTTPException(status_code=409, detail="A sync is already in progress.")
        _sync_in_progress = True
    try:
        return _run_full_steam_sync("manual")
    finally:
        with _sync_lock:
            _sync_in_progress = False


@app.get("/api/sync/status")
def api_sync_status():
    last = get_last_sync_run()
    next_run = None
    if scheduler.running:
        job = scheduler.get_job("steam_sync")
        if job and job.next_run_time:
            next_run = job.next_run_time.isoformat()
    last_run = None
    if last:
        last_run = {
            "started_at": str(last[1]) if last[1] else None,
            "finished_at": str(last[2]) if last[2] else None,
            "games_synced": last[3] or 0,
            "errors": last[4] or 0,
            "trigger": last[5],
        }
    return {
        "in_progress": _sync_in_progress,
        "last_run": last_run,
        "next_run_at": next_run,
        "steam_configured": bool(os.getenv("STEAM_API_KEY") and os.getenv("STEAM_ID")),
    }
