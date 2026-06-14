-- Migration 001 — make MyGameShelf multi-tenant.
--
-- Adds user_id to every user-owned table and a user_profiles table.
-- Run this ONCE against an existing single-user database.
--
-- HOW TO RUN (psql):
--   1. Find your Supabase user UUID (Supabase dashboard → Authentication → Users).
--   2. Replace the placeholder below, then run the whole file in a transaction.
--
--   psql "$DATABASE_URL" -v owner_id="'00000000-0000-0000-0000-000000000000'" -f db/migrations/001_multi_tenant.sql
--
-- If you have no existing data worth keeping, you can skip the backfill UPDATEs
-- and instead TRUNCATE the tables before adding the NOT NULL constraints.

BEGIN;

CREATE TABLE IF NOT EXISTS user_profiles (
    user_id     UUID PRIMARY KEY,
    steam_id    VARCHAR(32),
    created_at  TIMESTAMP DEFAULT NOW()
);

-- 1) Add columns as NULLABLE first so existing rows don't violate NOT NULL.
ALTER TABLE games        ADD COLUMN IF NOT EXISTS user_id UUID;
ALTER TABLE sessions     ADD COLUMN IF NOT EXISTS user_id UUID;
ALTER TABLE wishlist     ADD COLUMN IF NOT EXISTS user_id UUID;
ALTER TABLE achievements ADD COLUMN IF NOT EXISTS user_id UUID;
ALTER TABLE sync_runs    ADD COLUMN IF NOT EXISTS user_id UUID;

-- 2) Backfill existing rows to the original owner. Edit :owner_id (see header).
UPDATE games        SET user_id = :owner_id WHERE user_id IS NULL;
UPDATE sessions     SET user_id = :owner_id WHERE user_id IS NULL;
UPDATE wishlist     SET user_id = :owner_id WHERE user_id IS NULL;
UPDATE achievements SET user_id = :owner_id WHERE user_id IS NULL;
UPDATE sync_runs    SET user_id = :owner_id WHERE user_id IS NULL;

-- 3) Now enforce NOT NULL.
ALTER TABLE games        ALTER COLUMN user_id SET NOT NULL;
ALTER TABLE sessions     ALTER COLUMN user_id SET NOT NULL;
ALTER TABLE wishlist     ALTER COLUMN user_id SET NOT NULL;
ALTER TABLE achievements ALTER COLUMN user_id SET NOT NULL;
ALTER TABLE sync_runs    ALTER COLUMN user_id SET NOT NULL;

-- 4) Indexes for the per-user filters.
CREATE INDEX IF NOT EXISTS idx_games_user        ON games(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user     ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_wishlist_user     ON wishlist(user_id);
CREATE INDEX IF NOT EXISTS idx_achievements_user ON achievements(user_id);
CREATE INDEX IF NOT EXISTS idx_achievements_game ON achievements(game_id);
CREATE INDEX IF NOT EXISTS idx_sync_runs_user    ON sync_runs(user_id);

COMMIT;
