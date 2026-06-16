"""Postgres-backed job queue for Steam sync.

The existing Postgres database doubles as a durable work queue — no Redis or
extra infrastructure. Design:

* ``enqueue_sync`` inserts a job; a partial unique index guarantees at most one
  active (queued/running) job per user, so concurrent enqueues (e.g. several API
  instances all running the scheduler) collapse to one via ``ON CONFLICT``.
* ``claim_next_job`` claims the oldest queued job with ``FOR UPDATE SKIP LOCKED``
  so multiple worker processes can run in parallel and never grab the same job.
* ``reclaim_stale_jobs`` requeues jobs orphaned by a crashed worker.

All functions follow the same connection pattern as ``db/models.py`` and rely on
the pooled ``get_connection()``.
"""
import json
from typing import Optional

from db.connection import get_connection


def enqueue_sync(user_id: str, trigger: str) -> Optional[int]:
    """Queue a sync job for a user.

    Returns the new job id, or ``None`` if the user already has an active
    (queued or running) job — the partial unique index turns the duplicate
    INSERT into a no-op.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO sync_jobs (user_id, trigger)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
                RETURNING id
                """,
                (user_id, trigger),
            )
            row = cur.fetchone()
        conn.commit()
        return row[0] if row else None
    finally:
        conn.close()


def claim_next_job() -> Optional[tuple]:
    """Atomically claim the oldest queued job.

    Returns ``(job_id, user_id, trigger)`` or ``None`` if the queue is empty.
    The ``FOR UPDATE SKIP LOCKED`` makes this safe to call from many workers at
    once — each gets a different job.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE sync_jobs
                SET status = 'running', started_at = NOW(),
                    locked_at = NOW(), attempts = attempts + 1
                WHERE id = (
                    SELECT id FROM sync_jobs
                    WHERE status = 'queued'
                    ORDER BY enqueued_at
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                RETURNING id, user_id, trigger
                """
            )
            row = cur.fetchone()
        conn.commit()
        if not row:
            return None
        return (row[0], str(row[1]), row[2])
    finally:
        conn.close()


def complete_job(job_id: int, result: dict) -> None:
    """Mark a job done and store its result payload."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE sync_jobs SET status='done', result=%s, finished_at=NOW() WHERE id=%s",
                (json.dumps(result), job_id),
            )
        conn.commit()
    finally:
        conn.close()


def fail_job(job_id: int, error: str) -> None:
    """Mark a job failed and store a (truncated) error message."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE sync_jobs SET status='error', error=%s, finished_at=NOW() WHERE id=%s",
                (error[:2000], job_id),
            )
        conn.commit()
    finally:
        conn.close()


def get_active_job(user_id: str) -> Optional[dict]:
    """Return the user's active (queued/running) job, or None."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, status, trigger, enqueued_at, started_at
                FROM sync_jobs
                WHERE user_id = %s AND status IN ('queued', 'running')
                ORDER BY enqueued_at
                LIMIT 1
                """,
                (user_id,),
            )
            row = cur.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "status": row[1],
            "trigger": row[2],
            "enqueued_at": str(row[3]) if row[3] else None,
            "started_at": str(row[4]) if row[4] else None,
        }
    finally:
        conn.close()


def reclaim_stale_jobs(timeout_minutes: int = 30) -> int:
    """Requeue jobs stuck in 'running' past the timeout (worker likely crashed).

    Returns the number of jobs requeued. The timeout is generous on purpose so a
    long-but-healthy sync is never requeued out from under a live worker.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE sync_jobs
                SET status='queued', started_at=NULL, locked_at=NULL
                WHERE status='running'
                  AND locked_at < NOW() - make_interval(mins => %s)
                """,
                (timeout_minutes,),
            )
            n = cur.rowcount
        conn.commit()
        return n
    finally:
        conn.close()
