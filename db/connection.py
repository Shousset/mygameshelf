import os
import threading

import psycopg2
from psycopg2 import extensions as _ext
from psycopg2 import pool as _pgpool
from dotenv import load_dotenv

from db.context import get_current_user_id

load_dotenv()

# A single, process-wide connection pool. Built lazily on first use so that
# importing this module never opens a socket (keeps tests/CLI tools cheap and
# preserves the old behaviour of only failing when a connection is requested).
_pool = None
_pool_lock = threading.Lock()


def _build_pool():
    """Create the ThreadedConnectionPool from .env credentials."""
    password = os.getenv("DB_PASSWORD")
    if not password:
        raise RuntimeError(
            "DB_PASSWORD is not set. Copy .env.example to .env and fill in your local Postgres credentials."
        )

    minconn = int(os.getenv("DB_POOL_MIN", "1"))
    maxconn = int(os.getenv("DB_POOL_MAX", "10"))

    kwargs = dict(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", 5432)),
        dbname=os.getenv("DB_NAME", "mygameshelf"),
        user=os.getenv("DB_USER", "postgres"),
        password=password,
    )
    # Managed Postgres (Supabase, RDS, …) requires SSL. Opt-in via env so local
    # dev keeps working unchanged.
    sslmode = os.getenv("DB_SSLMODE")
    if sslmode:
        kwargs["sslmode"] = sslmode

    # ThreadedConnectionPool (not SimpleConnectionPool): FastAPI runs sync
    # endpoints in a threadpool and the APScheduler sync job runs in its own
    # thread, so the pool must be thread-safe.
    return _pgpool.ThreadedConnectionPool(minconn, maxconn, **kwargs)


def _get_pool():
    """Return the process-wide pool, building it on first use (thread-safe)."""
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = _build_pool()
    return _pool


class _PooledConnection:
    """Transparent wrapper around a pooled psycopg2 connection.

    The whole codebase uses the pattern::

        conn = get_connection()
        try:
            with conn.cursor() as cur:
                ...
            conn.commit()
        finally:
            conn.close()

    By making ``.close()`` return the connection to the pool instead of really
    closing it, every existing call site keeps working unchanged — no edits to
    models.py / api/main.py needed. All other attributes (``cursor``,
    ``commit``, ``rollback``, ``info``, …) are delegated to the real connection.
    """

    __slots__ = ("_conn", "_pool", "_released")

    def __init__(self, conn, pool):
        object.__setattr__(self, "_conn", conn)
        object.__setattr__(self, "_pool", pool)
        object.__setattr__(self, "_released", False)

    def close(self):
        """Return the underlying connection to the pool (idempotent)."""
        if object.__getattribute__(self, "_released"):
            return
        object.__setattr__(self, "_released", True)
        conn = object.__getattribute__(self, "_conn")
        pool = object.__getattribute__(self, "_pool")
        try:
            # Never hand back a connection with a dangling or aborted
            # transaction — the next borrower would inherit it. Reset first.
            if conn.info.transaction_status != _ext.TRANSACTION_STATUS_IDLE:
                conn.rollback()
        except Exception:
            # Connection is unusable; drop it from the pool entirely so the
            # pool replaces it with a fresh one next time.
            try:
                pool.putconn(conn, close=True)
            except Exception:
                pass
            return
        try:
            pool.putconn(conn)
        except Exception:
            pass

    def __getattr__(self, name):
        # Only called when normal attribute lookup fails (i.e. not a slot or
        # method defined here) — delegate to the wrapped connection.
        return getattr(object.__getattribute__(self, "_conn"), name)

    def __setattr__(self, name, value):
        # Forward attribute writes (e.g. conn.autocommit = True) to the real
        # connection; the wrapper's own slots are set via object.__setattr__.
        setattr(object.__getattribute__(self, "_conn"), name, value)

    def __enter__(self):
        # psycopg2 connections support `with conn:` as a transaction block that
        # commits/rolls back on exit but does NOT close. Mirror that, returning
        # the wrapper so the connection still comes back to the pool on .close().
        object.__getattribute__(self, "_conn").__enter__()
        return self

    def __exit__(self, exc_type, exc, tb):
        return object.__getattribute__(self, "_conn").__exit__(exc_type, exc, tb)


def get_connection():
    """Borrow a pooled psycopg2 connection.

    Sets the ``app.current_user_id`` session GUC (read by RLS policies) to the
    current request's user — or '' when there is none — on EVERY borrow, and
    commits it immediately so it's durable for the whole checkout and never
    leaks to the next borrower of a recycled connection. Pooled connections are
    reused, so this per-borrow reset is what makes RLS safe with the pool.

    Call ``.close()`` on the returned object when done to return it to the pool
    (the existing try/finally call sites already do this).
    """
    pool = _get_pool()
    raw = pool.getconn()
    uid = get_current_user_id()
    try:
        with raw.cursor() as cur:
            cur.execute("SELECT set_config('app.current_user_id', %s, false)", (uid or "",))
        raw.commit()
    except Exception:
        # Never hand back a connection whose tenant GUC may be half-set.
        try:
            pool.putconn(raw, close=True)
        except Exception:
            pass
        raise
    return _PooledConnection(raw, pool)


def close_all_connections():
    """Close every pooled connection and tear down the pool.

    Call on application shutdown. Safe to call when no pool was ever built.
    """
    global _pool
    with _pool_lock:
        if _pool is not None:
            try:
                _pool.closeall()
            finally:
                _pool = None


def initialize_schema():
    """Run schema.sql to create tables if they don't exist."""
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        sql = f.read()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    finally:
        conn.close()
