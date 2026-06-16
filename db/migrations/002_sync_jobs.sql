-- Migration 002 — Postgres-backed job queue for Steam sync.
--
-- Replaces the in-process APScheduler-runs-sync model with a durable queue:
-- the scheduler (and the manual "Sync now" button) enqueue jobs here, and a
-- separate worker process claims and runs them with FOR UPDATE SKIP LOCKED.
-- This lets sync scale across multiple worker processes and survives multiple
-- API instances without duplicating work.
--
-- Safe to run multiple times (all statements are IF NOT EXISTS).
--
--   psql "$DATABASE_URL" -f db/migrations/002_sync_jobs.sql

BEGIN;

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

CREATE UNIQUE INDEX IF NOT EXISTS uq_sync_jobs_active_per_user
    ON sync_jobs(user_id) WHERE status IN ('queued', 'running');

CREATE INDEX IF NOT EXISTS idx_sync_jobs_queued
    ON sync_jobs(enqueued_at) WHERE status = 'queued';

COMMIT;
