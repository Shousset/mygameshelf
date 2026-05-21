-- MyGameShelf Database Schema

CREATE TABLE IF NOT EXISTS games (
    id          SERIAL PRIMARY KEY,
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

CREATE TABLE IF NOT EXISTS sync_runs (
    id            SERIAL PRIMARY KEY,
    started_at    TIMESTAMP DEFAULT NOW(),
    finished_at   TIMESTAMP,
    games_synced  INT DEFAULT 0,
    errors        INT DEFAULT 0,
    trigger       VARCHAR(20)
);

CREATE TABLE IF NOT EXISTS sessions (
    id       SERIAL PRIMARY KEY,
    game_id  INT NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    date     DATE DEFAULT CURRENT_DATE,
    hours    NUMERIC(5,1) NOT NULL CHECK (hours > 0),
    notes    TEXT
);

CREATE TABLE IF NOT EXISTS wishlist (
    id       SERIAL PRIMARY KEY,
    title    VARCHAR(255) NOT NULL,
    platform VARCHAR(100),
    priority VARCHAR(10) NOT NULL DEFAULT 'Medium'
                CHECK (priority IN ('Low', 'Medium', 'High')),
    notes    TEXT,
    added_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS achievements (
    id SERIAL PRIMARY KEY,
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
