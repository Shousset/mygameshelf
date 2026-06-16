"""Shared, user-independent Steam metadata cache + daily API usage counter.

The achievement schema, global rarity percentages, and genre/release-year for a
Steam game are identical for everyone who owns it. We cache them by ``appid``
(never by user) so a game owned by thousands of users costs one set of Steam
calls instead of thousands. Each artifact has its own ``*_fetched_at`` so the
caller can apply a per-artifact TTL (schema changes rarely, rarity slowly,
genre/year almost never).

``steam_api_usage`` is a per-day call counter shared across all workers, used by
the throttle (api/steam_http.py) to enforce a daily budget on the shared key.

A cached value of "empty" (e.g. a game with no achievements -> ``[]``) is stored
and returned as-is so we don't keep re-fetching games that simply have nothing.
Getters return ``None`` ONLY when there is no fresh cache entry.
"""
import json
from typing import Optional

from db.connection import get_connection


# ─── Achievement schema (GetSchemaForGame) ────────────────────────────────────

def get_cached_schema(appid: str, ttl_seconds: int) -> Optional[list]:
    """Return the cached achievement-schema list (possibly empty), or None if
    absent/stale."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT schema_json FROM steam_app_cache
                WHERE appid = %s AND schema_fetched_at IS NOT NULL
                  AND schema_fetched_at > NOW() - make_interval(secs => %s)
                """,
                (appid, ttl_seconds),
            )
            row = cur.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def set_cached_schema(appid: str, schema: list) -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO steam_app_cache (appid, schema_json, schema_fetched_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (appid) DO UPDATE
                    SET schema_json = EXCLUDED.schema_json,
                        schema_fetched_at = EXCLUDED.schema_fetched_at
                """,
                (appid, json.dumps(schema)),
            )
        conn.commit()
    finally:
        conn.close()


# ─── Global rarity % (GetGlobalAchievementPercentagesForApp) ──────────────────

def get_cached_global_pct(appid: str, ttl_seconds: int) -> Optional[dict]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT global_pct_json FROM steam_app_cache
                WHERE appid = %s AND global_fetched_at IS NOT NULL
                  AND global_fetched_at > NOW() - make_interval(secs => %s)
                """,
                (appid, ttl_seconds),
            )
            row = cur.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def set_cached_global_pct(appid: str, pct_map: dict) -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO steam_app_cache (appid, global_pct_json, global_fetched_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (appid) DO UPDATE
                    SET global_pct_json = EXCLUDED.global_pct_json,
                        global_fetched_at = EXCLUDED.global_fetched_at
                """,
                (appid, json.dumps(pct_map)),
            )
        conn.commit()
    finally:
        conn.close()


# ─── Genre + release year (Store appdetails) ──────────────────────────────────

def get_cached_appdetails(appid: str, ttl_seconds: int) -> Optional[dict]:
    """Return ``{"genre": str|None, "year": int|None}`` if cached & fresh, else
    None. Note a fresh entry may legitimately hold null genre/year."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT genre, year FROM steam_app_cache
                WHERE appid = %s AND appdetails_fetched_at IS NOT NULL
                  AND appdetails_fetched_at > NOW() - make_interval(secs => %s)
                """,
                (appid, ttl_seconds),
            )
            row = cur.fetchone()
        if not row:
            return None
        return {"genre": row[0], "year": row[1]}
    finally:
        conn.close()


def set_cached_appdetails(appid: str, genre: Optional[str], year: Optional[int]) -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO steam_app_cache (appid, genre, year, appdetails_fetched_at)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (appid) DO UPDATE
                    SET genre = EXCLUDED.genre,
                        year = EXCLUDED.year,
                        appdetails_fetched_at = EXCLUDED.appdetails_fetched_at
                """,
                (appid, genre, year),
            )
        conn.commit()
    finally:
        conn.close()


# ─── Daily API usage counter ──────────────────────────────────────────────────

def record_steam_calls(n: int = 1) -> None:
    """Increment today's Steam API call counter by n."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO steam_api_usage (day, calls)
                VALUES (CURRENT_DATE, %s)
                ON CONFLICT (day) DO UPDATE
                    SET calls = steam_api_usage.calls + EXCLUDED.calls
                """,
                (n,),
            )
        conn.commit()
    finally:
        conn.close()


def steam_calls_today() -> int:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT calls FROM steam_api_usage WHERE day = CURRENT_DATE")
            row = cur.fetchone()
        return int(row[0]) if row else 0
    finally:
        conn.close()
