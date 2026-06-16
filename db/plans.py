"""Subscription plans and per-user limit enforcement.

The only gated limit today is library size (number of games): free is capped,
pro is unlimited. Limits live in the `plans` table (data, not code), so tuning
them is an UPDATE, not a deploy.

``max_games = NULL`` means unlimited; the helpers below normalise that to
``None`` and a ``remaining`` quota of ``None``.
"""
from typing import Optional

from db.connection import get_connection

DEFAULT_PLAN = "free"


def get_user_plan(user_id: str) -> str:
    """Return the user's plan name (defaults to 'free' if no profile yet)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT plan FROM user_profiles WHERE user_id = %s", (user_id,))
            row = cur.fetchone()
        return (row[0] if row and row[0] else DEFAULT_PLAN)
    finally:
        conn.close()


def set_user_plan(user_id: str, plan: str) -> None:
    """Upsert the user's plan (used by tests now; by billing webhooks later)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_profiles (user_id, plan) VALUES (%s, %s)
                ON CONFLICT (user_id) DO UPDATE SET plan = EXCLUDED.plan
                """,
                (user_id, plan),
            )
        conn.commit()
    finally:
        conn.close()


def _plan_max_games(plan: str) -> Optional[int]:
    """Max games for a plan (None = unlimited, also if the plan row is missing)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT max_games FROM plans WHERE name = %s", (plan,))
            row = cur.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def count_user_games(user_id: str) -> int:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM games WHERE user_id = %s", (user_id,))
            return int(cur.fetchone()[0])
    finally:
        conn.close()


def get_plan_and_usage(user_id: str) -> dict:
    """Plan + current library usage for the /api/plan endpoint and UI."""
    plan = get_user_plan(user_id)
    max_games = _plan_max_games(plan)
    used = count_user_games(user_id)
    remaining = None if max_games is None else max(0, max_games - used)
    return {
        "plan": plan,
        "max_games": max_games,          # None = unlimited
        "games_used": used,
        "games_remaining": remaining,    # None = unlimited
    }


def remaining_game_quota(user_id: str) -> Optional[int]:
    """How many more games the user may add. None = unlimited.

    Used to enforce the cap on add/import. Computed from the live game count, so
    it's always accurate even if games were deleted.
    """
    max_games = _plan_max_games(get_user_plan(user_id))
    if max_games is None:
        return None
    return max(0, max_games - count_user_games(user_id))
