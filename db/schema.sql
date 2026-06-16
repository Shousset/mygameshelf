-- MyGameShelf Database Schema (multi-tenant)
--
-- Every user-owned row carries a `user_id` (the Supabase auth user UUID). Queries
-- always filter by it so one user can never see or touch another's data.
-- No FK to auth.users so the schema stays portable if the DB is ever moved off Supabase.

-- Subscription plans. Limits are DATA (tune them without code changes).
-- max_games NULL = unlimited. The 'pro' tier is unlimited; 'free' is capped.
CREATE TABLE IF NOT EXISTS plans (
    name      VARCHAR(20) PRIMARY KEY,
    max_games INT,                 -- NULL = unlimited
    label     VARCHAR(50)
);
INSERT INTO plans (name, max_games, label) VALUES
    ('free', 50,   'Free'),
    ('pro',  NULL, 'Pro')
ON CONFLICT (name) DO NOTHING;

-- Per-user settings (e.g. their Steam ID). One row per authenticated user.
CREATE TABLE IF NOT EXISTS user_profiles (
    user_id     UUID PRIMARY KEY,
    steam_id    VARCHAR(32),
    plan        VARCHAR(20) NOT NULL DEFAULT 'free',
    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS games (
    id          SERIAL PRIMARY KEY,
    user_id     UUID NOT NULL,
    title       VARCHAR(255) NOT NULL,
    platform    VARCHAR(100),
    genre       VARCHAR(100),
    year        INT,
    status      VARCHAR(20) NOT NULL DEFAULT 'Backlog'
                    CHECK (status IN ('Backlog', 'Playing', 'Completed', 'Abandoned')),
    rating      NUMERIC(3,1) CHECK (rating >= 0 AND rating <= 10),
    hours_played NUMERIC(6,1) DEFAULT 0,
    notes       TEXT,
    external_id VARCHAR(100),
    last_synced_at  TIMESTAMP,
    last_sync_status VARCHAR(60),
    last_played_at  TIMESTAMP,
    added_at    TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_games_user ON games(user_id);

CREATE TABLE IF NOT EXISTS sync_runs (
    id            SERIAL PRIMARY KEY,
    user_id       UUID NOT NULL,
    started_at    TIMESTAMP DEFAULT NOW(),
    finished_at   TIMESTAMP,
    games_synced  INT DEFAULT 0,
    errors        INT DEFAULT 0,
    trigger       VARCHAR(20)
);
CREATE INDEX IF NOT EXISTS idx_sync_runs_user ON sync_runs(user_id);

-- Durable job queue for Steam sync, processed by the worker process(es).
-- Postgres IS the queue (no Redis/extra infra). Workers claim jobs with
-- SELECT ... FOR UPDATE SKIP LOCKED so several workers never grab the same job.
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
-- At most one ACTIVE (queued or running) job per user. This dedupes concurrent
-- enqueues at the DB level, so it's safe even if several API instances run the
-- scheduler at the same time — duplicate INSERTs collapse via ON CONFLICT.
CREATE UNIQUE INDEX IF NOT EXISTS uq_sync_jobs_active_per_user
    ON sync_jobs(user_id) WHERE status IN ('queued', 'running');
-- Fast poll for the worker: oldest queued job first.
CREATE INDEX IF NOT EXISTS idx_sync_jobs_queued
    ON sync_jobs(enqueued_at) WHERE status = 'queued';

CREATE TABLE IF NOT EXISTS sessions (
    id       SERIAL PRIMARY KEY,
    user_id  UUID NOT NULL,
    game_id  INT NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    date     DATE DEFAULT CURRENT_DATE,
    hours    NUMERIC(5,1) NOT NULL CHECK (hours > 0),
    notes    TEXT
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);

CREATE TABLE IF NOT EXISTS wishlist (
    id       SERIAL PRIMARY KEY,
    user_id  UUID NOT NULL,
    title    VARCHAR(255) NOT NULL,
    platform VARCHAR(100),
    priority VARCHAR(10) NOT NULL DEFAULT 'Medium'
                CHECK (priority IN ('Low', 'Medium', 'High')),
    notes    TEXT,
    added_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_wishlist_user ON wishlist(user_id);

CREATE TABLE IF NOT EXISTS achievements (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL,
    game_id INT NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    is_unlocked BOOLEAN DEFAULT FALSE,
    unlocked_at TIMESTAMP,
    icon_url VARCHAR(500),
    icon_gray_url VARCHAR(500),
    is_hidden BOOLEAN DEFAULT FALSE,
    global_pct NUMERIC(5,2)
);
CREATE INDEX IF NOT EXISTS idx_achievements_user ON achievements(user_id);
CREATE INDEX IF NOT EXISTS idx_achievements_game ON achievements(game_id);

-- Shared, user-independent Steam metadata cache (keyed by appid, NOT by user).
-- The achievement schema, global rarity %, and genre/year are identical for
-- every user who owns a game, so we fetch them once and reuse across all users.
-- This is what keeps a popular game (owned by thousands) from costing thousands
-- of identical Steam API calls. Each field has its own fetched_at for TTLs.
CREATE TABLE IF NOT EXISTS steam_app_cache (
    appid                 VARCHAR(20) PRIMARY KEY,
    schema_json           JSONB,
    global_pct_json       JSONB,
    genre                 VARCHAR(100),
    year                  INT,
    schema_fetched_at     TIMESTAMP,
    global_fetched_at     TIMESTAMP,
    appdetails_fetched_at TIMESTAMP
);

-- Daily counter of Steam Web API calls (the key is shared across all users, and
-- Steam caps ~100k calls/day per key). Lets the throttle enforce a daily budget
-- and gives us observability on how close we are to the cap.
CREATE TABLE IF NOT EXISTS steam_api_usage (
    day    DATE PRIMARY KEY,
    calls  INT NOT NULL DEFAULT 0
);
