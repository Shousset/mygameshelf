from db.connection import get_connection


# ─── GAMES ────────────────────────────────────────────────────────────────────

def add_game(title, platform, genre, year, status="Backlog", notes="", external_id=None):
    sql = """
        INSERT INTO games (title, platform, genre, year, status, notes, external_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id;
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (title, platform, genre, year, status, notes, external_id))
            game_id = cur.fetchone()[0]
        conn.commit()
        return game_id
    finally:
        conn.close()


def list_games(status_filter=None):
    sql = "SELECT id, title, platform, genre, year, status, rating, hours_played, external_id FROM games"
    params = ()
    if status_filter:
        sql += " WHERE status = %s"
        params = (status_filter,)
    sql += " ORDER BY added_at DESC;"
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()
    finally:
        conn.close()


def get_game(game_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM games WHERE id = %s;", (game_id,))
            return cur.fetchone()
    finally:
        conn.close()


def update_game_status(game_id, new_status):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE games SET status = %s WHERE id = %s;",
                (new_status, game_id),
            )
        conn.commit()
    finally:
        conn.close()


def rate_game(game_id, rating, notes):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE games SET rating = %s, notes = %s WHERE id = %s;",
                (rating, notes, game_id),
            )
        conn.commit()
    finally:
        conn.close()


def delete_game(game_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM games WHERE id = %s;", (game_id,))
        conn.commit()
    finally:
        conn.close()


# ─── SESSIONS ─────────────────────────────────────────────────────────────────

def log_session(game_id, hours, notes=""):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO sessions (game_id, hours, notes) VALUES (%s, %s, %s);",
                (game_id, hours, notes),
            )
            cur.execute(
                "UPDATE games SET hours_played = hours_played + %s WHERE id = %s;",
                (hours, game_id),
            )
        conn.commit()
    finally:
        conn.close()


def get_sessions(game_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT date, hours, notes FROM sessions WHERE game_id = %s ORDER BY date DESC;",
                (game_id,),
            )
            return cur.fetchall()
    finally:
        conn.close()


# ─── WISHLIST ─────────────────────────────────────────────────────────────────

def add_to_wishlist(title, platform, priority="Medium", notes=""):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO wishlist (title, platform, priority, notes) VALUES (%s, %s, %s, %s);",
                (title, platform, priority, notes),
            )
        conn.commit()
    finally:
        conn.close()


def list_wishlist():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, title, platform, priority, notes FROM wishlist ORDER BY priority DESC, added_at DESC;"
            )
            return cur.fetchall()
    finally:
        conn.close()


def remove_from_wishlist(wish_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM wishlist WHERE id = %s;", (wish_id,))
        conn.commit()
    finally:
        conn.close()


# ─── ACHIEVEMENTS ─────────────────────────────────────────────────────────────

def add_achievement(game_id, title, description="", is_unlocked=False,
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
                    (game_id, title, description, is_unlocked, unlocked_at,
                     icon_url, icon_gray_url, is_hidden, global_pct)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
                """,
                (game_id, title, description, is_unlocked, unlocked_at,
                 icon_url, icon_gray_url, is_hidden, global_pct),
            )
            ach_id = cur.fetchone()[0]
        conn.commit()
        return ach_id
    finally:
        conn.close()

def list_achievements(game_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Sort: unlocked-newest-first, then locked-rarest-first (low pct = rare and harder = interesting)
            cur.execute(
                """
                SELECT id, game_id, title, description, is_unlocked, unlocked_at,
                       icon_url, icon_gray_url, is_hidden, global_pct
                FROM achievements
                WHERE game_id = %s
                ORDER BY is_unlocked DESC,
                         unlocked_at DESC NULLS LAST,
                         global_pct ASC NULLS LAST,
                         id ASC;
                """,
                (game_id,),
            )
            return cur.fetchall()
    finally:
        conn.close()

def toggle_achievement(ach_id, is_unlocked):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            time_sql = "NOW()" if is_unlocked else "NULL"
            cur.execute(
                f"UPDATE achievements SET is_unlocked = %s, unlocked_at = {time_sql} WHERE id = %s;",
                (is_unlocked, ach_id),
            )
        conn.commit()
    finally:
        conn.close()

def clear_game_achievements(game_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM achievements WHERE game_id = %s;", (game_id,))
        conn.commit()
    finally:
        conn.close()

# ─── SYNC HELPERS ─────────────────────────────────────────────────────────────

def list_steam_games_with_appid():
    """Return [(id, title, external_id, hours_played, genre, year), ...] for Steam games with an AppID set."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, title, external_id, hours_played, genre, year
                FROM games
                WHERE platform = 'Steam' AND external_id IS NOT NULL AND external_id <> '';
                """
            )
            return cur.fetchall()
    finally:
        conn.close()


def list_steam_games_missing_appid():
    """Return [(id, title), ...] for Steam games whose external_id is NULL/empty — to be backfilled by title match."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, title FROM games
                WHERE platform = 'Steam' AND (external_id IS NULL OR external_id = '');
                """
            )
            return cur.fetchall()
    finally:
        conn.close()


def set_game_external_id(game_id, external_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE games SET external_id = %s WHERE id = %s;",
                (external_id, game_id),
            )
        conn.commit()
    finally:
        conn.close()


def set_game_last_played(game_id, dt):
    """dt may be a datetime or None."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE games SET last_played_at = %s WHERE id = %s;",
                (dt, game_id),
            )
        conn.commit()
    finally:
        conn.close()


def get_game_local_stats(game_id):
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
                WHERE g.id = %s;
                """,
                (game_id,),
            )
            return cur.fetchone()
    finally:
        conn.close()


def set_game_metadata(game_id, genre=None, year=None):
    """Patch genre and/or year only if a value is provided. Empty strings count as 'do not touch'."""
    sets = []
    params: list = []
    if genre:
        sets.append("genre = %s")
        params.append(genre)
    if year:
        sets.append("year = %s")
        params.append(year)
    if not sets:
        return
    params.append(game_id)
    sql = f"UPDATE games SET {', '.join(sets)} WHERE id = %s;"
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, tuple(params))
        conn.commit()
    finally:
        conn.close()


def set_game_sync_meta(game_id, status):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE games SET last_synced_at = NOW(), last_sync_status = %s WHERE id = %s;",
                (status, game_id),
            )
        conn.commit()
    finally:
        conn.close()


def set_game_hours(game_id, hours):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE games SET hours_played = %s WHERE id = %s;",
                (hours, game_id),
            )
        conn.commit()
    finally:
        conn.close()


def start_sync_run(trigger):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO sync_runs (trigger) VALUES (%s) RETURNING id;",
                (trigger,),
            )
            run_id = cur.fetchone()[0]
        conn.commit()
        return run_id
    finally:
        conn.close()


def finish_sync_run(run_id, games_synced, errors):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE sync_runs SET finished_at = NOW(), games_synced = %s, errors = %s WHERE id = %s;",
                (games_synced, errors, run_id),
            )
        conn.commit()
    finally:
        conn.close()


def get_last_sync_run():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, started_at, finished_at, games_synced, errors, trigger
                FROM sync_runs
                ORDER BY started_at DESC
                LIMIT 1;
                """
            )
            return cur.fetchone()
    finally:
        conn.close()

# ─── STATS ────────────────────────────────────────────────────────────────────

def get_stats():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM games;")
            total_games = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM games WHERE status = 'Completed';")
            completed = cur.fetchone()[0]

            cur.execute("SELECT COALESCE(SUM(hours_played), 0) FROM games;")
            total_hours = cur.fetchone()[0]

            cur.execute(
                """
                SELECT genre, COUNT(*) AS cnt
                FROM games
                WHERE genre IS NOT NULL AND genre != ''
                GROUP BY genre
                ORDER BY cnt DESC
                LIMIT 1;
                """
            )
            row = cur.fetchone()
            top_genre = row[0] if row else "N/A"

            cur.execute("SELECT COUNT(*) FROM wishlist;")
            wishlist_count = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM achievements;")
            total_achievements = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM achievements WHERE is_unlocked = TRUE;")
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
