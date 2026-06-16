"""
MyGameShelf — FastAPI REST Backend (multi-tenant)
Run with: uvicorn api.main:app --reload --port 8000
(from the mygameshelf/ directory)

Every data endpoint requires a Supabase JWT (Authorization: Bearer <token>) and
is scoped to the authenticated user via the `user_id` dependency.
"""

from __future__ import annotations
import os
import re
import asyncio
from typing import Optional
from urllib.parse import urlencode

import httpx
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI, HTTPException, Depends, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Reuse existing DB logic
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from db.connection import initialize_schema, get_connection, close_all_connections
from db.jobs import enqueue_sync, get_active_job
from db.plans import get_plan_and_usage, remaining_game_quota
from db.steam_cache import (
    get_cached_schema, set_cached_schema,
    get_cached_global_pct, set_cached_global_pct,
    get_cached_appdetails, set_cached_appdetails,
    steam_calls_today,
)
from api.steam_http import steam_get, SteamBudgetExceeded

# Shared-cache TTLs (seconds). Schema almost never changes; global rarity drifts
# slowly; genre/year is effectively permanent. Override via env if needed.
STEAM_SCHEMA_TTL = int(os.getenv("STEAM_SCHEMA_TTL_SECONDS", str(30 * 24 * 3600)))      # 30d
STEAM_GLOBAL_TTL = int(os.getenv("STEAM_GLOBAL_TTL_SECONDS", str(7 * 24 * 3600)))       # 7d
STEAM_APPDETAILS_TTL = int(os.getenv("STEAM_APPDETAILS_TTL_SECONDS", str(90 * 24 * 3600)))  # 90d
from db.models import (
    add_game, list_games, get_game, update_game_status, rate_game, delete_game,
    log_session, get_sessions,
    add_to_wishlist, list_wishlist, remove_from_wishlist,
    get_stats,
    list_steam_games_with_appid, list_steam_games_missing_appid, set_game_external_id,
    set_game_sync_meta, set_game_metadata, set_game_last_played, get_game_local_stats,
    start_sync_run, finish_sync_run, get_last_sync_run,
    add_achievement, list_achievements, toggle_achievement, clear_game_achievements,
    ensure_user_profile, get_user_steam_id, set_user_steam_id, list_users_with_steam,
)
from api.auth import get_current_user, extract_user_id
from db.context import set_current_user, clear_current_user

app = FastAPI(title="MyGameShelf API", version="2.0.0")

# CORS — restrict to the deployed frontend(s). Configure via ALLOWED_ORIGINS (comma-separated).
_allowed_env = os.getenv("ALLOWED_ORIGINS")
_allowed = _allowed_env or "http://localhost:3000"
ALLOWED_ORIGINS = [o.strip() for o in _allowed.split(",") if o.strip()]
# Base URL of the frontend — used as the OpenID realm / return_to for "Sign in
# through Steam". Defaults to the first allowed origin.
FRONTEND_URL = (os.getenv("FRONTEND_URL") or (ALLOWED_ORIGINS[0] if ALLOWED_ORIGINS else "http://localhost:3000")).rstrip("/")
# In production the localhost default will silently block the real frontend — warn loudly
# so a forgotten env var is caught in the deploy logs instead of as a mystery CORS error.
if not _allowed_env:
    print(
        "[WARNING] ALLOWED_ORIGINS is not set — defaulting to http://localhost:3000. "
        "Set it to your deployed frontend URL(s) before publishing."
    )
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TenantContextMiddleware:
    """Pure-ASGI middleware that sets the per-request tenant context from the
    Bearer token, so the DB layer can apply RLS (db.context -> app.current_user_id).

    Pure ASGI (not BaseHTTPMiddleware) on purpose: it runs in the same task as the
    endpoint, so the ContextVar it sets is copied into FastAPI's sync threadpool
    where get_connection() reads it. Non-fatal: unauthenticated requests just get
    an empty context (RLS then returns no rows for tenant tables).
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope.get("headers") or [])
            raw_auth = headers.get(b"authorization")
            set_current_user(extract_user_id(raw_auth.decode("latin-1") if raw_auth else None))
            try:
                await self.app(scope, receive, send)
            finally:
                clear_current_user()
        else:
            await self.app(scope, receive, send)


app.add_middleware(TenantContextMiddleware)


# ─── SCHEDULER ────────────────────────────────────────────────────────────────
# The scheduler no longer runs syncs in-process; it just enqueues jobs into the
# Postgres-backed queue (db/jobs.py), which the worker process(es) drain. The
# old in-memory per-user lock is gone — the sync_jobs partial unique index now
# guarantees one active job per user across every process.

scheduler = BackgroundScheduler()


@app.on_event("startup")
def on_startup():
    try:
        # PRE-MIGRATION for legacy single-tenant DBs: ensure the multi-tenant
        # `user_id` column exists on every table BEFORE initialize_schema() runs,
        # because schema.sql creates `CREATE INDEX ... ON games(user_id)` which
        # fails on an old table that predates the column — and that failure would
        # otherwise abort the whole schema init (so the columns would never get
        # added). `ALTER TABLE IF EXISTS` is a no-op on a fresh DB.
        try:
            pre = get_connection()
            try:
                with pre.cursor() as cur:
                    for _t in ("games", "sessions", "wishlist", "achievements", "sync_runs"):
                        cur.execute(f"ALTER TABLE IF EXISTS {_t} ADD COLUMN IF NOT EXISTS user_id UUID;")
                pre.commit()
            finally:
                pre.close()
        except Exception as e:
            print(f"[WARNING] user_id pre-migration failed: {e}")

        initialize_schema()
        # LIVE PATCHES for older DBs predating these columns/tables.
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
                # Multi-tenant columns (nullable here; migration 001 enforces NOT NULL after backfill).
                cur.execute("ALTER TABLE games ADD COLUMN IF NOT EXISTS user_id UUID;")
                cur.execute("ALTER TABLE sessions ADD COLUMN IF NOT EXISTS user_id UUID;")
                cur.execute("ALTER TABLE wishlist ADD COLUMN IF NOT EXISTS user_id UUID;")
                cur.execute("ALTER TABLE achievements ADD COLUMN IF NOT EXISTS user_id UUID;")
                cur.execute("ALTER TABLE sync_runs ADD COLUMN IF NOT EXISTS user_id UUID;")
                # Job queue (migration 002) — create here too so existing DBs get it.
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS sync_jobs (
                        id          BIGSERIAL PRIMARY KEY,
                        user_id     UUID NOT NULL,
                        trigger     VARCHAR(20) NOT NULL,
                        status      VARCHAR(20) NOT NULL DEFAULT 'queued'
                                        CHECK (status IN ('queued', 'running', 'done', 'error')),
                        result      JSONB,
                        error       TEXT,
                        attempts    INT NOT NULL DEFAULT 0,
                        enqueued_at TIMESTAMP NOT NULL DEFAULT NOW(),
                        started_at  TIMESTAMP,
                        finished_at TIMESTAMP,
                        locked_at   TIMESTAMP
                    );
                    """
                )
                cur.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_sync_jobs_active_per_user "
                    "ON sync_jobs(user_id) WHERE status IN ('queued', 'running');"
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_sync_jobs_queued "
                    "ON sync_jobs(enqueued_at) WHERE status = 'queued';"
                )
                # Shared Steam metadata cache + daily usage counter (migration 003).
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS steam_app_cache (
                        appid                 VARCHAR(20) PRIMARY KEY,
                        schema_json           JSONB,
                        global_pct_json       JSONB,
                        genre                 VARCHAR(100),
                        year                  INT,
                        schema_fetched_at     TIMESTAMP,
                        global_fetched_at     TIMESTAMP,
                        appdetails_fetched_at TIMESTAMP
                    );
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS steam_api_usage (
                        day    DATE PRIMARY KEY,
                        calls  INT NOT NULL DEFAULT 0
                    );
                    """
                )
                # Subscription plans + per-user plan (migration 005).
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS plans (
                        name      VARCHAR(20) PRIMARY KEY,
                        max_games INT,
                        label     VARCHAR(50)
                    );
                    """
                )
                cur.execute(
                    """
                    INSERT INTO plans (name, max_games, label) VALUES
                        ('free', 50, 'Free'), ('pro', NULL, 'Pro')
                    ON CONFLICT (name) DO NOTHING;
                    """
                )
                cur.execute(
                    "ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS plan VARCHAR(20) NOT NULL DEFAULT 'free';"
                )
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        print(f"[WARNING] Could not initialize schema: {e}")

    # Boot the background scheduler — runs Steam sync every 6h for every user with a SteamID.
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
    # Release every pooled DB connection so Postgres doesn't keep idle sockets.
    close_all_connections()


# ─── PYDANTIC MODELS ──────────────────────────────────────────────────────────

class GameCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    platform: str = Field("", max_length=100)
    genre: str = Field("", max_length=100)
    year: Optional[int] = Field(None, ge=1950, le=2100)
    status: str = "Backlog"
    notes: str = Field("", max_length=5000)

class StatusUpdate(BaseModel):
    status: str

class RatingUpdate(BaseModel):
    rating: float = Field(..., ge=0, le=10)
    notes: str = Field("", max_length=5000)

class SessionCreate(BaseModel):
    hours: float = Field(..., gt=0, le=10000)
    notes: str = Field("", max_length=5000)

class WishlistCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    platform: str = Field("", max_length=100)
    priority: str = "Medium"
    notes: str = Field("", max_length=5000)

class AchievementCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field("", max_length=2000)

class AchievementToggle(BaseModel):
    is_unlocked: bool

class SteamImportRequest(BaseModel):
    # api_key is NO LONGER accepted from the client — the server holds one key.
    steam_id: str = Field(..., min_length=1, max_length=32)
    dry_run: bool = False

class BulkImport(BaseModel):
    titles: list[str]
    platform: str = Field(..., max_length=100)


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def _row_to_game(row) -> dict:
    keys = ["id", "title", "platform", "genre", "year", "status", "rating", "hours_played", "external_id"]
    if row is None:
        return {}
    # list_games returns 9 cols; get_game returns all cols. Note: get_game's first
    # column is id, so slicing [:9] would include user_id — instead map explicitly.
    return dict(zip(keys, row[:9]))


def _get_steam_api_key() -> Optional[str]:
    return os.getenv("STEAM_API_KEY")


# ─── GAMES ────────────────────────────────────────────────────────────────────

@app.get("/api/games")
def api_list_games(status: Optional[str] = None, user_id: str = Depends(get_current_user)):
    rows = list_games(user_id, status)
    return [_row_to_game(r) for r in rows]


@app.get("/api/plan")
def api_get_plan(user_id: str = Depends(get_current_user)):
    """The user's plan and library usage (for the Settings UI and upgrade prompts)."""
    return get_plan_and_usage(user_id)


@app.post("/api/games", status_code=201)
def api_add_game(body: GameCreate, user_id: str = Depends(get_current_user)):
    quota = remaining_game_quota(user_id)
    if quota is not None and quota <= 0:
        raise HTTPException(
            status_code=403,
            detail="You've reached your plan's library limit. Upgrade to Pro for unlimited games.",
        )
    gid = add_game(user_id, body.title, body.platform, body.genre, body.year, body.status, body.notes)
    return {"id": gid}


@app.get("/api/games/{game_id}")
def api_get_game(game_id: int, user_id: str = Depends(get_current_user)):
    row = get_game(user_id, game_id)
    if not row:
        raise HTTPException(status_code=404, detail="Game not found")
    # get_game returns SELECT *; column order:
    # 0 id, 1 user_id, 2 title, 3 platform, 4 genre, 5 year, 6 status,
    # 7 rating, 8 hours_played, 9 notes, 10 external_id, ...
    return {
        "id": row[0],
        "title": row[2],
        "platform": row[3],
        "genre": row[4],
        "year": row[5],
        "status": row[6],
        "rating": row[7],
        "hours_played": row[8],
        "external_id": row[10],
    }


@app.put("/api/games/{game_id}/status")
def api_update_status(game_id: int, body: StatusUpdate, user_id: str = Depends(get_current_user)):
    valid = ["Backlog", "Playing", "Completed", "Abandoned"]
    if body.status not in valid:
        raise HTTPException(status_code=400, detail=f"Status must be one of {valid}")
    if not get_game(user_id, game_id):
        raise HTTPException(status_code=404, detail="Game not found")
    update_game_status(user_id, game_id, body.status)
    return {"ok": True}


@app.put("/api/games/{game_id}/rating")
def api_rate_game(game_id: int, body: RatingUpdate, user_id: str = Depends(get_current_user)):
    if not get_game(user_id, game_id):
        raise HTTPException(status_code=404, detail="Game not found")
    rate_game(user_id, game_id, body.rating, body.notes)
    return {"ok": True}


@app.delete("/api/games/{game_id}")
def api_delete_game(game_id: int, user_id: str = Depends(get_current_user)):
    if not get_game(user_id, game_id):
        raise HTTPException(status_code=404, detail="Game not found")
    delete_game(user_id, game_id)
    return {"ok": True}


# ─── SESSIONS ─────────────────────────────────────────────────────────────────

@app.get("/api/games/{game_id}/sessions")
def api_get_sessions(game_id: int, user_id: str = Depends(get_current_user)):
    rows = get_sessions(user_id, game_id)
    return [{"date": str(r[0]), "hours": float(r[1]), "notes": r[2]} for r in rows]


@app.post("/api/games/{game_id}/sessions", status_code=201)
def api_log_session(game_id: int, body: SessionCreate, user_id: str = Depends(get_current_user)):
    if not get_game(user_id, game_id):
        raise HTTPException(status_code=404, detail="Game not found")
    log_session(user_id, game_id, body.hours, body.notes)
    return {"ok": True}


# ─── WISHLIST ─────────────────────────────────────────────────────────────────

@app.get("/api/wishlist")
def api_list_wishlist(user_id: str = Depends(get_current_user)):
    rows = list_wishlist(user_id)
    keys = ["id", "title", "platform", "priority", "notes"]
    return [dict(zip(keys, r)) for r in rows]


@app.post("/api/wishlist", status_code=201)
def api_add_wishlist(body: WishlistCreate, user_id: str = Depends(get_current_user)):
    if body.priority not in ("Low", "Medium", "High"):
        raise HTTPException(status_code=400, detail="Priority must be Low, Medium or High")
    add_to_wishlist(user_id, body.title, body.platform, body.priority, body.notes)
    return {"ok": True}


@app.delete("/api/wishlist/{wish_id}")
def api_remove_wishlist(wish_id: int, user_id: str = Depends(get_current_user)):
    remove_from_wishlist(user_id, wish_id)
    return {"ok": True}


# ─── ACHIEVEMENTS ─────────────────────────────────────────────────────────────

@app.get("/api/games/{game_id}/achievements")
def api_list_achievements(game_id: int, user_id: str = Depends(get_current_user)):
    rows = list_achievements(user_id, game_id)
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
def api_add_achievement(game_id: int, body: AchievementCreate, user_id: str = Depends(get_current_user)):
    if not get_game(user_id, game_id):
        raise HTTPException(status_code=404, detail="Game not found")
    ach_id = add_achievement(user_id, game_id, body.title, body.description)
    return {"id": ach_id}


@app.put("/api/achievements/{ach_id}/toggle")
def api_toggle_achievement(ach_id: int, body: AchievementToggle, user_id: str = Depends(get_current_user)):
    if not toggle_achievement(user_id, ach_id, body.is_unlocked):
        raise HTTPException(status_code=404, detail="Achievement not found")
    return {"ok": True}


@app.post("/api/games/{game_id}/sync_steam")
async def api_sync_steam_achievements(game_id: int, user_id: str = Depends(get_current_user)):
    game = get_game(user_id, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    # get_game returns SELECT *; external_id is the last data column. Index by name-safety:
    # columns: id, user_id, title, platform, genre, year, status, rating, hours_played, notes, external_id, ...
    external_id = game[10]
    if not external_id:
        raise HTTPException(status_code=400, detail="Game has no Steam AppID attached. Maybe delete and re-import this game from Steam?")

    api_key = _get_steam_api_key()
    steam_id = get_user_steam_id(user_id)
    if not api_key:
        raise HTTPException(status_code=400, detail="Server STEAM_API_KEY is not configured.")
    if not steam_id:
        raise HTTPException(status_code=400, detail="No SteamID saved for your account. Import from Steam first.")

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
    player_map = {a["apiname"]: a for a in player_achs}

    global_pct_map = {}
    for gp in (g_data.get("achievementpercentages") or {}).get("achievements", []):
        try:
            global_pct_map[gp["name"]] = float(gp["percent"])
        except (KeyError, TypeError, ValueError):
            pass

    clear_game_achievements(user_id, game_id)
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
            user_id, game_id, name, desc, unlocked,
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
def api_get_stats(user_id: str = Depends(get_current_user)):
    return get_stats(user_id)


# ─── IMPORTS ──────────────────────────────────────────────────────────────────

STEAM_OWNED_URL = "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/"

@app.post("/api/import/steam")
async def api_import_steam(body: SteamImportRequest, user_id: str = Depends(get_current_user)):
    api_key = _get_steam_api_key()
    if not api_key:
        raise HTTPException(status_code=400, detail="Server STEAM_API_KEY is not configured.")

    params = {
        "key": api_key,
        "steamid": body.steam_id,
        "include_appinfo": "true",
        "include_played_free_games": "true",
        "format": "json",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(STEAM_OWNED_URL, params=params)

    if resp.status_code != 200:
        error_text = resp.text[:150].strip() if resp.text else "No extra details"
        raise HTTPException(status_code=502, detail=f"Steam API rejected the request (Error {resp.status_code}): {error_text}")

    data = resp.json()
    games_raw = data.get("response", {}).get("games", [])

    if not games_raw:
        return {"imported": 0, "games": [], "message": "No games found — check your SteamID and that your profile is public."}

    # Persist this user's SteamID so sync/profile endpoints can use it later.
    if not body.dry_run:
        set_user_steam_id(user_id, body.steam_id)

    existing_titles = {r[1].lower() for r in list_games(user_id)}
    quota = remaining_game_quota(user_id)  # None = unlimited
    preview = []
    imported = 0
    would_add = 0
    limit_reached = 0

    for g in games_raw:
        name = g.get("name", "Unknown")
        appid = str(g.get("appid", ""))
        hours = round(g.get("playtime_forever", 0) / 60, 1)
        is_existing = name.lower() in existing_titles
        over_limit = False
        if not is_existing:
            would_add += 1
            over_limit = quota is not None and would_add > quota
        preview.append({"title": name, "hours_played": hours, "platform": "Steam",
                        "skipped": is_existing, "over_limit": over_limit})

        if not is_existing and over_limit:
            limit_reached += 1
            continue
        if not body.dry_run and not is_existing:
            gid = add_game(user_id, title=name, platform="Steam", genre="", year=None, status="Backlog", notes="", external_id=appid)
            if hours > 0:
                log_session(user_id, gid, hours, "Imported from Steam")
            imported += 1

    msg = f"Found {len(games_raw)} games on Steam. "
    if body.dry_run:
        msg += "(Dry run — nothing saved)"
    else:
        msg += f"Imported {imported} new games."
    if limit_reached:
        msg += f" {limit_reached} skipped — plan library limit reached (upgrade to Pro for unlimited)."

    return {
        "imported": imported if not body.dry_run else 0,
        "games": preview,
        "skipped_due_to_limit": limit_reached,
        "message": msg,
    }


def _bulk_import(body: BulkImport, user_id: str) -> dict:
    """Shared bulk-paste import (Epic/PSN), enforcing the plan's library cap.

    Imports up to the remaining quota and reports how many were left out because
    the plan limit was reached, so the user gets a clear upgrade signal instead
    of a hard failure mid-list.
    """
    existing_titles = {r[1].lower() for r in list_games(user_id)}
    quota = remaining_game_quota(user_id)  # None = unlimited
    imported = 0
    skipped = []
    limit_reached = 0

    for title in body.titles:
        title = title.strip()
        if not title:
            continue
        if title.lower() in existing_titles:
            skipped.append(title)
            continue
        if quota is not None and imported >= quota:
            limit_reached += 1
            continue
        add_game(user_id, title=title, platform=body.platform, genre="", year=None, status="Backlog", notes="")
        existing_titles.add(title.lower())
        imported += 1

    resp = {"imported": imported, "skipped": skipped}
    if limit_reached:
        resp["skipped_due_to_limit"] = limit_reached
        resp["message"] = (
            f"Imported {imported}. {limit_reached} not imported — your plan's library "
            f"limit was reached. Upgrade to Pro for unlimited games."
        )
    return resp


@app.post("/api/import/epic")
def api_import_epic(body: BulkImport, user_id: str = Depends(get_current_user)):
    return _bulk_import(body, user_id)


@app.post("/api/import/psn")
def api_import_psn(body: BulkImport, user_id: str = Depends(get_current_user)):
    return _bulk_import(body, user_id)


# ─── PER-GAME STATS + REFRESH ─────────────────────────────────────────────────

@app.get("/api/games/{game_id}/steam-stats")
def api_steam_stats(game_id: int, user_id: str = Depends(get_current_user)):
    """Local stats panel for the per-game Sessions view. No Steam calls — uses the DB."""
    row = get_game_local_stats(user_id, game_id)
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
def api_refresh_game(game_id: int, user_id: str = Depends(get_current_user)):
    """Refresh one game from Steam: playtime delta, achievements, genre/year, last_played."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT title, platform, genre, year, hours_played, external_id FROM games WHERE id = %s AND user_id = %s;",
                (game_id, user_id),
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

    api_key = _get_steam_api_key()
    steam_id = get_user_steam_id(user_id)
    if not api_key:
        raise HTTPException(status_code=400, detail="Server STEAM_API_KEY is not configured.")
    if not steam_id:
        raise HTTPException(status_code=400, detail="No SteamID saved for your account. Import from Steam first.")

    with httpx.Client(timeout=30) as client:
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
            print(f"[refresh] appid {external_id} missing from GetOwnedGames response — skipping playtime/last_played update")

        try:
            _sync_one_steam_game(
                user_id, game_id, str(external_id), hours_played, genre, year,
                api_key, steam_id, owned_index, client,
            )
            _enrich_genre_year(user_id, game_id, str(external_id), genre, year, client)
            set_game_sync_meta(user_id, game_id, "ok")
        except httpx.TimeoutException:
            set_game_sync_meta(user_id, game_id, "timeout")
            raise HTTPException(status_code=504, detail="Steam timed out — try again in a moment.")
        except Exception as e:
            set_game_sync_meta(user_id, game_id, f"error: {type(e).__name__[:30]}"[:60])
            raise HTTPException(status_code=502, detail=f"Refresh failed: {e}")

    return api_steam_stats(game_id, user_id)


@app.get("/api/dashboard/feed")
def api_dashboard_feed(user_id: str = Depends(get_current_user)):
    """Returns: currently-playing (most recent last_played) + last unlocks across the user's library."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, title, platform, external_id, hours_played, last_played_at
                FROM games
                WHERE user_id = %s AND last_played_at IS NOT NULL
                ORDER BY last_played_at DESC
                LIMIT 1;
                """,
                (user_id,),
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
                    WHERE game_id = %s AND user_id = %s AND is_unlocked = TRUE
                    ORDER BY unlocked_at DESC NULLS LAST
                    LIMIT 5;
                    """,
                    (cp_id, user_id),
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
                WHERE a.user_id = %s AND a.is_unlocked = TRUE AND a.unlocked_at IS NOT NULL
                ORDER BY a.unlocked_at DESC
                LIMIT 8;
                """,
                (user_id,),
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
async def api_steam_profile(user_id: str = Depends(get_current_user)):
    """Returns the user's Steam avatar, name, profile URL."""
    api_key = _get_steam_api_key()
    steam_id = get_user_steam_id(user_id)
    if not api_key:
        raise HTTPException(status_code=400, detail="Server STEAM_API_KEY is not configured.")
    if not steam_id:
        raise HTTPException(status_code=400, detail="No SteamID saved for your account.")

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


# ─── STEAM OPENID (\"Sign in through Steam\") ──────────────────────────────────
# Links a Steam account to the already-authenticated app user by capturing their
# SteamID64 via OpenID 2.0 — no manual 17-digit ID entry. This does NOT replace
# app login (that's Supabase); identity comes from the Bearer token, never the URL.

STEAM_OPENID_ENDPOINT = "https://steamcommunity.com/openid/login"
_STEAM_CLAIMED_ID_RE = re.compile(r"^https://steamcommunity\.com/openid/id/(\d+)$")


@app.get("/api/steam/openid/login")
def api_steam_openid_login(user_id: str = Depends(get_current_user)):
    """Return the Steam OpenID URL to redirect the browser to.

    return_to points back at the frontend, which then POSTs the openid.* params
    to /api/steam/openid/verify with the user's Bearer token.
    """
    return_to = f"{FRONTEND_URL}/settings"
    params = {
        "openid.ns": "http://specs.openid.net/auth/2.0",
        "openid.mode": "checkid_setup",
        "openid.return_to": return_to,
        "openid.realm": FRONTEND_URL,
        "openid.identity": "http://specs.openid.net/auth/2.0/identifier_select",
        "openid.claimed_id": "http://specs.openid.net/auth/2.0/identifier_select",
    }
    return {"redirect_url": f"{STEAM_OPENID_ENDPOINT}?{urlencode(params)}"}


def _verify_steam_openid(params: dict) -> Optional[str]:
    """Verify an OpenID assertion with Steam and return the SteamID64, or None.

    Re-sends the params back to Steam with mode=check_authentication; Steam
    answers `is_valid:true` only for assertions it actually issued (blocks forged
    params). Also pins return_to to our own frontend to prevent replay.
    """
    if (params.get("openid.return_to") or "").split("?", 1)[0] != f"{FRONTEND_URL}/settings":
        return None
    claimed_id = params.get("openid.claimed_id") or ""
    m = _STEAM_CLAIMED_ID_RE.match(claimed_id)
    if not m:
        return None

    # Echo every openid.* field back, only flipping the mode.
    payload = {k: v for k, v in params.items() if k.startswith("openid.")}
    payload["openid.mode"] = "check_authentication"
    try:
        with httpx.Client(timeout=10) as client:
            r = client.post(STEAM_OPENID_ENDPOINT, data=payload)
    except httpx.HTTPError:
        return None
    if r.status_code != 200 or "is_valid:true" not in r.text:
        return None
    return m.group(1)


@app.post("/api/steam/openid/verify")
def api_steam_openid_verify(params: dict = Body(...), user_id: str = Depends(get_current_user)):
    """Verify the OpenID response and save the SteamID for the current user."""
    steam_id = _verify_steam_openid(params)
    if not steam_id:
        raise HTTPException(status_code=400, detail="Steam sign-in could not be verified.")
    set_user_steam_id(user_id, steam_id)
    return {"ok": True, "steam_id": steam_id}


# ─── STEAM RECENTLY PLAYED ────────────────────────────────────────────────────

STEAM_RECENT_URL = "https://api.steampowered.com/IPlayerService/GetRecentlyPlayedGames/v0001/"


@app.get("/api/steam/recently-played")
async def api_steam_recently_played(user_id: str = Depends(get_current_user)):
    """Pull last-2-weeks playtime from Steam, joined to the user's local game rows by AppID."""
    api_key = _get_steam_api_key()
    steam_id = get_user_steam_id(user_id)
    if not api_key:
        raise HTTPException(status_code=400, detail="Server STEAM_API_KEY is not configured.")
    if not steam_id:
        raise HTTPException(status_code=400, detail="No SteamID saved for your account.")

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

    local_by_appid = {}
    for r in list_steam_games_with_appid(user_id):
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
    """Cheap liveness probe used by the frontend to detect backend availability. Unauthenticated."""
    db_ok = True
    try:
        conn = get_connection()
        conn.close()
    except Exception:
        db_ok = False
    # steam_configured here reflects only whether the SERVER has an API key.
    steam_configured = bool(_get_steam_api_key())
    return {"ok": db_ok, "db": db_ok, "steam_configured": steam_configured}


STEAM_APPDETAILS_URL = "https://store.steampowered.com/api/appdetails"


def _fetch_steam_appdetails(appid: str, client) -> dict:
    """Hit the public Steam Store API. Returns the inner `data` dict or {} on failure."""
    try:
        r = steam_get(client, STEAM_APPDETAILS_URL, params={"appids": appid, "l": "en"})
        if r is None or r.status_code != 200:
            return {}
        payload = r.json() or {}
        entry = payload.get(str(appid)) or {}
        if not entry.get("success"):
            return {}
        return entry.get("data") or {}
    except Exception:
        return {}


def _enrich_genre_year(user_id, game_id, appid, current_genre, current_year, client):
    """Fill in genre + release year if missing, using the shared appid cache first.

    Returns True only if a network call to Steam was actually made (cache misses);
    a cache hit returns False so the caller knows no Steam quota was spent.
    """
    needs_genre = not (current_genre and str(current_genre).strip())
    needs_year = current_year is None
    if not (needs_genre or needs_year):
        return False

    # Shared cache first — genre/year are identical for every owner of this app.
    cached = get_cached_appdetails(appid, STEAM_APPDETAILS_TTL)
    if cached is not None:
        g = cached["genre"] if needs_genre else None
        y = cached["year"] if needs_year else None
        if g or y:
            set_game_metadata(user_id, game_id, genre=g, year=y)
        return False  # served from cache, no Steam call

    data = _fetch_steam_appdetails(appid, client)
    if not data:
        return True  # call was made even if we got nothing useful

    # Parse BOTH fields (not just the ones this user needs) so the shared cache
    # is complete for the next user who owns this game.
    genres = data.get("genres") or []
    names = [g.get("description") for g in genres if g.get("description")]
    parsed_genre = ", ".join(names)[:100] if names else None

    rd = (data.get("release_date") or {}).get("date") or ""
    import re
    m = re.search(r"\b(19|20)\d{2}\b", rd)
    parsed_year = int(m.group(0)) if m else None

    set_cached_appdetails(appid, parsed_genre, parsed_year)

    new_genre = parsed_genre if needs_genre else None
    new_year = parsed_year if needs_year else None
    if new_genre or new_year:
        set_game_metadata(user_id, game_id, genre=new_genre, year=new_year)
    return True


def _sync_one_steam_game(user_id, game_id, appid, current_hours, current_genre, current_year, api_key, steam_id, owned_index, client):
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
            log_session(user_id, game_id, delta, "Auto-sync from Steam")
        rtime = int(info.get("rtime_last_played", 0) or 0)
        if rtime > 0:
            try:
                set_game_last_played(user_id, game_id, datetime.fromtimestamp(rtime))
            except Exception as e:
                print(f"[sync] last_played write failed for {game_id}: {e}")

    # 2) Achievements — schema + global rarity are user-independent (cached by
    #    appid and shared across all users); only player progress is per-user.
    player_url = f"https://api.steampowered.com/ISteamUserStats/GetPlayerAchievements/v0001/?appid={appid}&key={api_key}&steamid={steam_id}"

    # --- Achievement schema (shared cache) ---
    ach_schema = get_cached_schema(appid, STEAM_SCHEMA_TTL)
    if ach_schema is None:
        schema_url = f"https://api.steampowered.com/ISteamUserStats/GetSchemaForGame/v2/?key={api_key}&appid={appid}"
        s_res = steam_get(client, schema_url)
        if s_res is None or s_res.status_code != 200:
            return 0  # game has no public schema — not an error
        try:
            ach_schema = s_res.json()["game"]["availableGameStats"]["achievements"]
        except KeyError:
            set_cached_schema(appid, [])  # cache "no achievements" to skip future refetches
            return 0
        set_cached_schema(appid, ach_schema)
    if not ach_schema:
        return 0

    # --- Player progress (per-user, always fetched) ---
    p_res = steam_get(client, player_url)
    p_data = p_res.json() if (p_res is not None and p_res.status_code == 200) else {}
    player_achs = p_data.get("playerstats", {}).get("achievements", [])
    player_map = {a["apiname"]: a for a in player_achs}

    # --- Global rarity % (shared cache) ---
    global_pct_map = get_cached_global_pct(appid, STEAM_GLOBAL_TTL)
    if global_pct_map is None:
        global_url = f"https://api.steampowered.com/ISteamUserStats/GetGlobalAchievementPercentagesForApp/v2/?gameid={appid}&format=json"
        g_res = steam_get(client, global_url)
        g_data = g_res.json() if (g_res is not None and g_res.status_code == 200) else {}
        global_pct_map = {}
        for gp in (g_data.get("achievementpercentages") or {}).get("achievements", []):
            try:
                global_pct_map[gp["name"]] = float(gp["percent"])
            except (KeyError, TypeError, ValueError):
                pass
        set_cached_global_pct(appid, global_pct_map)

    clear_game_achievements(user_id, game_id)
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
            user_id, game_id, name, desc, unlocked,
            icon_url=a.get("icon"),
            icon_gray_url=a.get("icongray"),
            is_hidden=bool(a.get("hidden")),
            unlocked_at=unlocked_at,
            global_pct=global_pct_map.get(apiname),
        )
        count += 1
    return count


def _run_full_steam_sync(user_id: str, trigger: str) -> dict:
    """Full Steam sync over one user's games with an AppID. Callable from threadpool/scheduler."""
    api_key = _get_steam_api_key()
    steam_id = get_user_steam_id(user_id)
    if not api_key or not steam_id:
        return {"ok": False, "synced": 0, "errors": 0, "message": "Steam not configured for this user."}

    run_id = start_sync_run(user_id, trigger)
    synced = 0
    errors = 0
    backfilled = 0

    # Guard the whole run: any unexpected failure (DB error, network blowup outside
    # the per-game loop) must still close out the sync_runs row, otherwise it stays
    # marked "in progress" forever and /api/sync/status reports a stuck run.
    try:
        with httpx.Client(timeout=30) as client:
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

            if owned_index:
                by_title = {(g.get("name") or "").strip().lower(): str(g.get("appid"))
                            for g in owned_index.values() if g.get("appid")}
                for (gid, title) in list_steam_games_missing_appid(user_id):
                    appid = by_title.get((title or "").strip().lower())
                    if appid:
                        set_game_external_id(user_id, gid, appid)
                        backfilled += 1
                if backfilled:
                    print(f"[sync] Backfilled external_id for {backfilled} game(s) by title match")

            games = list_steam_games_with_appid(user_id)
            if not games:
                finish_sync_run(user_id, run_id, 0, 0)
                return {"ok": True, "synced": 0, "errors": 0, "backfilled": backfilled, "message": "No Steam-linked games to sync."}

            for (gid, _title, appid, current_hours, current_genre, current_year) in games:
                try:
                    _sync_one_steam_game(
                        user_id, gid, str(appid), current_hours, current_genre, current_year,
                        api_key, steam_id, owned_index, client,
                    )
                    _enrich_genre_year(user_id, gid, str(appid), current_genre, current_year, client)
                    set_game_sync_meta(user_id, gid, "ok")
                    synced += 1
                except SteamBudgetExceeded:
                    # Shared daily quota spent — stop cleanly; remaining games are
                    # picked up on the next run. (steam_get short-circuits before
                    # any network call, so this is cheap.)
                    print(f"[sync] daily Steam budget reached — deferring remaining games for {user_id}")
                    try:
                        set_game_sync_meta(user_id, gid, "deferred: daily budget")
                    except Exception:
                        pass
                    break
                except Exception as e:
                    if isinstance(e, httpx.TimeoutException):
                        tag = "timeout"
                    elif isinstance(e, httpx.HTTPError):
                        tag = "http_error"
                    else:
                        tag = "error"
                    detail = type(e).__name__[:30]
                    try:
                        set_game_sync_meta(user_id, gid, f"{tag}: {detail}"[:60])
                    except Exception as meta_e:
                        print(f"[sync] failed to record error for game {gid}: {meta_e}")
                    errors += 1

        finish_sync_run(user_id, run_id, synced, errors)
        return {"ok": True, "synced": synced, "errors": errors, "backfilled": backfilled, "trigger": trigger}
    except Exception:
        # Close the run row before propagating so the user isn't stuck behind a
        # phantom "sync in progress" state.
        try:
            finish_sync_run(user_id, run_id, synced, errors)
        except Exception as fin_e:
            print(f"[sync] failed to finalize stuck run {run_id}: {fin_e}")
        raise


def _scheduled_steam_sync():
    """APScheduler entrypoint — enqueue a sync job for every user with a SteamID.

    The actual work runs in the worker process(es) (see worker.py). Enqueuing is
    cheap and the sync_jobs unique index dedupes, so this is safe even if several
    API instances run the scheduler at the same time.
    """
    if not _get_steam_api_key():
        print("[scheduler] Skip — no server STEAM_API_KEY configured")
        return
    queued = 0
    for (uid, _steam_id) in list_users_with_steam():
        try:
            if enqueue_sync(str(uid), "scheduler") is not None:
                queued += 1
        except Exception as e:
            print(f"[scheduler] enqueue failed for {uid}: {e}")
    print(f"[scheduler] enqueued {queued} sync job(s)")


@app.post("/api/sync/all", status_code=202)
def api_sync_all(user_id: str = Depends(get_current_user)):
    """Queue a full Steam sync for the current user.

    Returns immediately (202); the worker runs the sync in the background. Poll
    /api/sync/status for progress and the final result.
    """
    job_id = enqueue_sync(user_id, "manual")
    if job_id is None:
        raise HTTPException(status_code=409, detail="A sync is already queued or in progress.")
    return {"ok": True, "queued": True, "job_id": job_id}


@app.get("/api/sync/status")
def api_sync_status(user_id: str = Depends(get_current_user)):
    last = get_last_sync_run(user_id)
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
    active = get_active_job(user_id)
    try:
        calls_today = steam_calls_today()
    except Exception:
        calls_today = None
    saved_steam_id = get_user_steam_id(user_id)
    return {
        "in_progress": active is not None,
        "active_job": active,
        "last_run": last_run,
        "next_run_at": next_run,
        "steam_configured": bool(_get_steam_api_key() and saved_steam_id),
        "steam_linked": bool(saved_steam_id),
        "steam_calls_today": calls_today,
    }
