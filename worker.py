"""Steam sync worker — drains the Postgres-backed ``sync_jobs`` queue.

Run as a SEPARATE process from the API:

    python worker.py

Scale horizontally by starting several of them; ``FOR UPDATE SKIP LOCKED`` in
``db.jobs.claim_next_job`` guarantees no two workers ever process the same job.

Env knobs (all optional):
    WORKER_POLL_SECONDS   how often to poll when the queue is empty (default 5)
    WORKER_STALE_MINUTES  requeue jobs stuck 'running' this long (default 30)

NOTE: this imports the sync engine from api.main. That also imports the FastAPI
app object, but importing does not start the server or the scheduler (those only
run under uvicorn's lifecycle). A future cleanup is to extract the sync engine
into its own module so the worker doesn't import the web layer at all.
"""
import os
import time

from db.jobs import claim_next_job, complete_job, fail_job, reclaim_stale_jobs
from db.connection import close_all_connections
from api.main import _run_full_steam_sync

POLL_INTERVAL = float(os.getenv("WORKER_POLL_SECONDS", "5"))
STALE_TIMEOUT_MIN = int(os.getenv("WORKER_STALE_MINUTES", "30"))
RECLAIM_EVERY_SECONDS = 60


def main() -> None:
    print(f"[worker] started — polling every {POLL_INTERVAL}s, stale timeout {STALE_TIMEOUT_MIN}min")
    last_reclaim = 0.0
    try:
        while True:
            # Periodically requeue jobs orphaned by a crashed worker.
            now = time.monotonic()
            if now - last_reclaim > RECLAIM_EVERY_SECONDS:
                try:
                    n = reclaim_stale_jobs(STALE_TIMEOUT_MIN)
                    if n:
                        print(f"[worker] reclaimed {n} stale job(s)")
                except Exception as e:
                    print(f"[worker] reclaim failed: {e}")
                last_reclaim = now

            try:
                job = claim_next_job()
            except Exception as e:
                print(f"[worker] claim failed: {e}")
                time.sleep(POLL_INTERVAL)
                continue

            if not job:
                time.sleep(POLL_INTERVAL)
                continue

            job_id, user_id, trigger = job
            print(f"[worker] job {job_id}: syncing user {user_id} ({trigger})")
            try:
                result = _run_full_steam_sync(user_id, trigger)
                complete_job(job_id, result)
                print(f"[worker] job {job_id} done: {result}")
            except Exception as e:
                msg = f"{type(e).__name__}: {e}"
                try:
                    fail_job(job_id, msg)
                except Exception as fe:
                    print(f"[worker] could not mark job {job_id} failed: {fe}")
                print(f"[worker] job {job_id} failed: {msg}")
    except KeyboardInterrupt:
        print("[worker] shutting down")
    finally:
        close_all_connections()


if __name__ == "__main__":
    main()
