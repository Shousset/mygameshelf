-- Migration 005 — subscription plans + per-user plan.
--
-- Introduces a configurable `plans` table (limits are data, not code) and a
-- `plan` column on user_profiles. The only gated limit for now is library size:
-- free = 50 games, pro = unlimited (max_games NULL). Tune the numbers by UPDATE-ing
-- the plans rows; no code change needed.
--
-- Safe to run multiple times.
--
--   psql "$DATABASE_URL" -f db/migrations/005_plans.sql

BEGIN;

CREATE TABLE IF NOT EXISTS plans (
    name      VARCHAR(20) PRIMARY KEY,
    max_games INT,                 -- NULL = unlimited
    label     VARCHAR(50)
);

INSERT INTO plans (name, max_games, label) VALUES
    ('free', 50,   'Free'),
    ('pro',  NULL, 'Pro')
ON CONFLICT (name) DO NOTHING;

ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS plan VARCHAR(20) NOT NULL DEFAULT 'free';

COMMIT;
