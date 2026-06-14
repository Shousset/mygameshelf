-- MyGameShelf Database Schema (multi-tenant)
--
-- Every user-owned row carries a `user_id` (the Supabase auth user UUID). Queries
-- always filter by it so one user can never see or touch another's data.
-- No FK to auth.users so the schema stays portable if the DB is ever moved off Supabase.

-- Per-user settings (e.g. their Steam ID). One row per authenticated user.
CREATE TABLE IF NOT EXISTS user_profiles (
    user_id     UUID PRIMARY KEY,
    steam_id    VARCHAR(32),
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
