"""Per-request tenant context.

Holds the current authenticated user's id in a ``ContextVar`` so the database
layer can set the ``app.current_user_id`` Postgres session GUC that Row-Level
Security policies read. The value is set by the FastAPI middleware (api/main.py)
at the start of each request; it is empty for unauthenticated requests and for
the worker process (which connects as a BYPASSRLS role and ignores RLS).

A ``ContextVar`` (not a thread-local) is used on purpose: FastAPI runs sync
endpoints in a worker thread via anyio, which COPIES the current context into
that thread. Setting the var in middleware (async context) therefore makes it
visible to ``get_connection()`` inside the sync endpoint.
"""
from contextvars import ContextVar
from typing import Optional

_current_user_id: ContextVar[Optional[str]] = ContextVar("current_user_id", default=None)


def set_current_user(user_id: Optional[str]) -> None:
    _current_user_id.set(user_id)


def get_current_user_id() -> Optional[str]:
    return _current_user_id.get()


def clear_current_user() -> None:
    _current_user_id.set(None)
