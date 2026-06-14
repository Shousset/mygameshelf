"""
Data access for MyGameShelf — MULTI-TENANT.

Every function takes `user_id` (the Supabase auth UUID) and scopes its query to
that user. SELECT/UPDATE/DELETE always include `AND user_id = %s`, and INSERTs
always write the user_id. This is what guarantees one user can never read or
mutate another user's rows, even when addressing a row by its primary key.
"""

from db.connection import get_connection


# ─── USER PROFILES ────────────────────────────────────────────────────────────

def ensure_user_profile(user_id):
    """Create the profile row on first sight (idempotent)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO user_profiles (user_id) VALUES (%s) ON CONFLICT (user_id) DO NOTHING;",
                (user_id,),
            )
        conn.commit()
    finally:
        conn.close()


def get_user_steam_id(user_id):
    """Return the user's saved SteamID, or None."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT steam_id FROM user_profiles WHERE user_id = %s;", (user_id,))
            row = cur.fetchone()
            return row[0] if row else None
    finally:
        conn.close()


def set_user_steam_id(user_id, steam_id):
    """Upsert the user's SteamID."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_profiles (user_id, steam_id) VALUES (%s, %s)
                ON CONFLICT (user_id) DO UPDATE SET steam_id = EXCLUDED.steam_id;
                """,
                (user_id, steam_id),
            )
        conn.commit()
    finally:
        conn.close()


def list_users_with_steam():
    """Return [(user_id, steam_id), ...] for every user that has a SteamID set.
    Used by the background scheduler to sync each user in turn."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT user_id, steam_id FROM user_profiles WHERE steam_id IS NOT NULL AND steam_id <> '';"
            )
            return cur.fetchall()
    finally:
        conn.close()


# ─── GAMES ────────────────────────────────────────────────────────────────────

def add_game(user_id, title, platform, genre, year, status="Backlog", notes="", external_id=None):
    sql = """
        INSERT INTO games (user_id, title, platform, genre, year, status, notes, external_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id;
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (user_id, title, platform, genre, year, status, notes, external_id))
            game_id = cur.fetchone()[0]
        conn.commit()
        return game_id
    finally:
        conn.close()


def list_games(user_id, status_filter=None):
    sql = "SELECT id, title, platform, genre, year, status, rating, hours_played, external_id FROM games WHERE user_id = %s"
    params = [user_id]
    if status_filter:
        sql += " AND status = %s"
        params.append(status_filter)
    sql += " ORDER BY added_at DESC;"
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            return cur.fetchall()
    finally:
        conn.close()


def get_game(user_id, game_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM games WHERE id = %s AND user_id = %s;", (game_id, user_id))
            return cur.fetchone()
    finally:
        conn.close()


def update_game_status(user_id, game_id, new_status):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE games SET status = %s WHERE id = %s AND user_id = %s;",
                (new_status, game_id, user_id),
            )
        conn.commit()
    finally:
        conn.close()


def rate_game(user_id, game_id, rating, notes):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE games SET rating = %s, notes = %s WHERE id = %s AND user_id = %s;",
                (rating, notes, game_id, user_id),
            )
        conn.commit()
    finally:
        conn.close()


def delete_game(user_id, game_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM games WHERE id = %s AND user_id = %s;", (game_id, user_id))
        conn.commit()
    finally:
        conn.close()


# ─── SESSIONS ─────────────────────────────────────────────────────────────────

def log_session(user_id, game_id, hours, notes=""):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Scope the games UPDATE by user_id so we only ever bump the caller's game.
            cur.execute(
                "UPDATE games SET hours_played = hours_played + %s WHERE id = %s AND user_id = %s;",
                (hours, game_id, user_id),
            )
            if cur.rowcount == 0:
                # Game doesn't belong to this user (or doesn't exist) — don't orphan a session.
                conn.rollback()
                raise PermissionError("Game not found for this user.")
            cur.execute(
                "INSERT INTO sessions (user_id, game_id, hours, notes) VALUES (%s, %s, %s, %s);",
                (user_id, game_id, hours, notes),
            )
        conn.commit()
    finally:
        conn.close()


def get_sessions(user_id, game_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT date, hours, notes FROM sessions WHERE game_id = %s AND user_id = %s ORDER BY date DESC;",
                (game_id, user_id),
            )
            return cur.fetchall()
    finally:
        conn.close()


# ─── WISHLIST ─────────────────────────────────────────────────────────────────

def add_to_wishlist(user_id, title, platform, priority="Medium", notes=""):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO wishlist (user_id, title, platform, priority, notes) VALUES (%s, %s, %s, %s, %s);",
                (user_id, title, platform, priority, notes),
            )
        conn.commit()
    finally:
        conn.close()


def list_wishlist(user_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, title, platform, priority, notes FROM wishlist WHERE user_id = %s ORDER BY priority DESC, added_at DESC;",
                (user_id,),
            )
            return cur.fetchall()
    finally:
        conn.close()


def remove_from_wishlist(user_id, wish_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM wishlist WHERE id = %s AND user_id = %s;", (wish_id, user_id))
        conn.commit()
    finally:
        conn.close()


# ─── ACHIEVEMENTS ─────────────────────────────────────────────────────────────

def add_achievement(user_id, game_id, title, description="", is_unlocked=False,
                    icon_url=None, icon_gray_url=None, is_hidden=False,
                    unlocked_at=None, global_pct=None):
    """If unlocked_at is provided (datetime), it overrides the default NOW()-when-unlocked behavior.
    This lets Steam sync record the real unlock time from `unlocktime` rather than the sync moment."""
    if unlocked_at is None and is_unlocked:
        from datetime import datetime
        unlocked_at = datetime.now()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO achievements
                    (user_id, game_id, title, description, is_unlocked, unlocked_at,
                     icon_url, icon_gray_url, is_hidden, global_pct)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
                """,
                (user_id, game_id, title, description, is_unlocked, unlocked_at,
                 icon_url, icon_gray_url, is_hidden, global_pct),
            )
            ach_id = cur.fetchone()[0]
        conn.commit()
        return ach_id
    finally:
        conn.close()


def list_achievements(user_id, game_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Sort: unlocked-newest-first, then locked-rarest-first (low pct = rare and harder = interesting)
            cur.execute(
                """
                SELECT id, game_id, title, description, is_unlocked, unlocked_at,
                       icon_url, icon_gray_url, is_hidden, global_pct
                FROM achievements
                WHERE game_id = %s AND user_id = %s
                ORDER BY is_unlocked DESC,
                         unlocked_at DESC NULLS LAST,
                         global_pct ASC NULLS LAST,
                         id ASC;
                """,
                (game_id, user_id),
            )
            return cur.fetchall()
    finally:
        conn.close()


def toggle_achievement(user_id, ach_id, is_unlocked):
    """Flip an achievement's unlocked state. Returns the number of rows updated
    (0 means the achievement doesn't exist or isn't owned by this user)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            time_sql = "NOW()" if is_unlocked else "NULL"
            cur.execute(
                f"UPDATE achievements SET is_unlocked = %s, unlocked_at = {time_sql} WHERE id = %s AND user_id = %s;",
                (is_unlocked, ach_id, user_id),
            )
            updated = cur.rowcount
        conn.commit()
        return updated
    finally:
        conn.close()


def clear_game_achievements(user_id, game_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM achievements WHERE game_id = %s AND user_id = %s;", (game_id, user_id))
        conn.commit()
    finally:
        conn.close()


# ─── SYNC HELPERS ─────────────────────────────────────────────────────────────

def list_steam_games_with_appid(user_id):
    """Return [(id, title, external_id, hours_played, genre, year), ...] for this user's Steam games with an AppID set."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, title, external_id, hours_played, genre, year
                FROM games
                WHERE user_id = %s AND platform = 'Steam'
                  AND external_id IS NOT NULL AND external_id <> '';
                """,
                (user_id,),
            )
            return cur.fetchall()
    finally:
        conn.close()


def list_steam_games_missing_appid(user_id):
    """Return [(id, title), ...] for this user's Steam games whose external_id is NULL/empty."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, title FROM games
                WHERE user_id = %s AND platform = 'Steam'
                  AND (external_id IS NULL OR external_id = '');
                """,
                (user_id,),
            )
            return cur.fetchall()
    finally:
        conn.close()


def set_game_external_id(user_id, game_id, external_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE games SET external_id = %s WHERE id = %s AND user_id = %s;",
                (external_id, game_id, user_id),
            )
        conn.commit()
    finally:
        conn.close()


def set_game_last_played(user_id, game_id, dt):
    """dt may be a datetime or None."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE games SET last_played_at = %s WHERE id = %s AND user_id = %s;",
                (dt, game_id, user_id),
            )
        conn.commit()
    finally:
        conn.close()


def get_game_local_stats(user_id, game_id):
    """Returns (hours_played, last_played_at, last_session_date, hours_2weeks, external_id, title, platform)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    g.hours_played,
                    g.last_played_at,
                    (SELECT MAX(date) FROM sessions WHERE game_id = g.id),
                    COALESCE((
                        SELECT SUM(hours) FROM sessions
                        WHERE game_id = g.id AND date >= CURRENT_DATE - INTERVAL '14 days'
                    ), 0),
                    g.external_id,
                    g.title,
                    g.platform
                FROM games g
                WHERE g.id = %s AND g.user_id = %s;
                """,
                (game_id, user_id),
            )
            return cur.fetchone()
    finally:
        conn.close()


def set_game_metadata(user_id, game_id, genre=None, year=None):
    """Patch genre and/or year only if a value is provided. Empty strings count as 'do not touch'."""
    sets = []
    params = []
    if genre:
        sets.append("genre = %s")
        params.append(genre)
    if year:
        sets.append("year = %s")
        params.append(year)
    if not sets:
        return
    params.append(game_id)
    params.append(user_id)
    # Note: the SET fragments are hardcoded literals above (never user input) — safe to interpolate.
    sql = f"UPDATE games SET {', '.join(sets)} WHERE id = %s AND user_id = %s;"
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, tuple(params))
        conn.commit()
    finally:
        conn.close()


def set_game_sync_meta(user_id, game_id, status):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE games SET last_synced_at = NOW(), last_sync_status = %s WHERE id = %s AND user_id = %s;",
                (status, game_id, user_id),
            )
        conn.commit()
    finally:
        conn.close()


def set_game_hours(user_id, game_id, hours):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE games SET hours_played = %s WHERE id = %s AND user_id = %s;",
                (hours, game_id, user_id),
            )
        conn.commit()
    finally:
        conn.close()


def start_sync_run(user_id, trigger):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO sync_runs (user_id, trigger) VALUES (%s, %s) RETURNING id;",
                (user_id, trigger),
            )
            run_id = cur.fetchone()[0]
        conn.commit()
        return run_id
    finally:
        conn.close()


def finish_sync_run(user_id, run_id, games_synced, errors):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE sync_runs SET finished_at = NOW(), games_synced = %s, errors = %s WHERE id = %s AND user_id = %s;",
                (games_synced, errors, run_id, user_id),
            )
        conn.commit()
    finally:
        conn.close()


def get_last_sync_run(user_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, started_at, finished_at, games_synced, errors, trigger
                FROM sync_runs
                WHERE user_id = %s
                ORDER BY started_at DESC
                LIMIT 1;
                """,
                (user_id,),
            )
            return cur.fetchone()
    finally:
        conn.close()


# ─── STATS ────────────────────────────────────────────────────────────────────

def get_stats(user_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM games WHERE user_id = %s;", (user_id,))
            total_games = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM games WHERE user_id = %s AND status = 'Completed';", (user_id,))
            completed = cur.fetchone()[0]

            cur.execute("SELECT COALESCE(SUM(hours_played), 0) FROM games WHERE user_id = %s;", (user_id,))
            total_hours = cur.fetchone()[0]

            cur.execute(
                """
                SELECT genre, COUNT(*) AS cnt
                FROM games
                WHERE user_id = %s AND genre IS NOT NULL AND genre != ''
                GROUP BY genre
                ORDER BY cnt DESC
                LIMIT 1;
                """,
                (user_id,),
            )
            row = cur.fetchone()
            top_genre = row[0] if row else "N/A"

            cur.execute("SELECT COUNT(*) FROM wishlist WHERE user_id = %s;", (user_id,))
            wishlist_count = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM achievements WHERE user_id = %s;", (user_id,))
            total_achievements = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM achievements WHERE user_id = %s AND is_unlocked = TRUE;", (user_id,))
            unlocked_achievements = cur.fetchone()[0]

        completion_pct = round((completed / total_games * 100), 1) if total_games else 0
        return {
            "total_games": total_games,
            "completed": completed,
            "completion_pct": completion_pct,
            "total_hours": float(total_hours),
            "top_genre": top_genre,
            "wishlist_count": wishlist_count,
            "total_achievements": total_achievements,
            "unlocked_achievements": unlocked_achievements,
        }
    finally:
        conn.close()
