"""Resilient, throttled HTTP helper for the Steam Web API.

Every Steam call in the sync engine goes through ``steam_get`` so we get, in one
place:

* **Throttle** — a minimum interval between calls (per process) so we never burst.
* **Backoff** — automatic retry on 429 / 5xx with exponential backoff, honouring
  ``Retry-After`` when Steam sends it.
* **Usage tracking** — every call increments a shared per-day counter
  (``steam_api_usage``) so the daily budget can be enforced across all workers.
* **Daily budget** — if ``STEAM_DAILY_BUDGET`` is set and reached, ``steam_get``
  raises ``SteamBudgetExceeded`` instead of making the call, so a sync stops
  cleanly rather than blowing the shared key's ~100k/day cap.

Config (all optional, via env):
    STEAM_MIN_INTERVAL_MS  min ms between calls in one process (default 300)
    STEAM_MAX_RETRIES      retries on 429/5xx before giving up (default 4)
    STEAM_DAILY_BUDGET     max calls/day across all workers; 0 disables (default 0)
"""
import os
import threading
import time

import httpx

from db.steam_cache import record_steam_calls, steam_calls_today

MIN_INTERVAL = float(os.getenv("STEAM_MIN_INTERVAL_MS", "300")) / 1000.0
MAX_RETRIES = int(os.getenv("STEAM_MAX_RETRIES", "4"))
DAILY_BUDGET = int(os.getenv("STEAM_DAILY_BUDGET", "0"))  # 0 = unlimited
_MAX_BACKOFF = 30.0
_BUDGET_CHECK_TTL = 30.0  # seconds between DB checks of today's usage


class SteamBudgetExceeded(Exception):
    """Raised when the shared daily Steam API budget has been reached."""


_throttle_lock = threading.Lock()
_last_call_at = 0.0
_budget = {"checked_at": 0.0, "over": False}


def _respect_min_interval() -> None:
    """Block just long enough to keep calls at most one per MIN_INTERVAL."""
    global _last_call_at
    with _throttle_lock:
        wait = MIN_INTERVAL - (time.monotonic() - _last_call_at)
        if wait > 0:
            time.sleep(wait)
        _last_call_at = time.monotonic()


def _budget_exceeded() -> bool:
    if DAILY_BUDGET <= 0:
        return False
    now = time.monotonic()
    # Cache the (DB-backed) count for a few seconds to avoid a query per call.
    if now - _budget["checked_at"] > _BUDGET_CHECK_TTL:
        try:
            _budget["over"] = steam_calls_today() >= DAILY_BUDGET
        except Exception:
            _budget["over"] = False
        _budget["checked_at"] = now
    return _budget["over"]


def steam_get(client: httpx.Client, url: str, *, params: dict | None = None):
    """GET a Steam endpoint with throttle, retry/backoff, and usage tracking.

    Returns the final ``httpx.Response`` (which may still be a 4xx/5xx if all
    retries were exhausted — callers handle non-200 the same as before).
    Raises ``SteamBudgetExceeded`` before calling if the daily budget is spent,
    and propagates network errors after exhausting retries.
    """
    if _budget_exceeded():
        raise SteamBudgetExceeded(f"Daily Steam API budget ({DAILY_BUDGET}) reached")

    backoff = 1.0
    response = None
    for attempt in range(MAX_RETRIES + 1):
        _respect_min_interval()
        try:
            response = client.get(url, params=params)
        except (httpx.TimeoutException, httpx.TransportError):
            if attempt < MAX_RETRIES:
                time.sleep(min(backoff, _MAX_BACKOFF))
                backoff = min(backoff * 2, _MAX_BACKOFF)
                continue
            raise
        finally:
            # Count the attempt against the daily budget even on transport error
            # only when a request actually went out (response is not None).
            if response is not None:
                try:
                    record_steam_calls(1)
                except Exception:
                    pass

        if response.status_code == 429 or 500 <= response.status_code < 600:
            if attempt < MAX_RETRIES:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if (retry_after and retry_after.isdigit()) else backoff
                time.sleep(min(delay, _MAX_BACKOFF))
                backoff = min(backoff * 2, _MAX_BACKOFF)
                response = None  # reset so the counter logic above is correct next loop
                continue

        return response

    return response
