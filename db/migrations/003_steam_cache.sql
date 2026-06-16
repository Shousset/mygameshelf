-- Migration 003 — shared Steam metadata cache + daily API usage counter.
--
-- The achievement schema, global rarity %, and genre/year for a game are the
-- same for every user who owns it. Caching them by appid (not per user) means a
-- game owned by thousands of users costs ONE set of Steam calls instead of
-- thousands — the single biggest reduction in Steam Web API usage.
--
-- steam_api_usage tracks calls/day so the throttle can enforce a daily budget
-- (the shared API key is capped ~100k calls/day).
--
-- Safe to run multiple times.
--
--   psql "$DATABASE_URL" -f db/migrations/003_steam_cache.sql

BEGIN;

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

CREATE TABLE IF NOT EXISTS steam_api_usage (
    day    DATE PRIMARY KEY,
    calls  INT NOT NULL DEFAULT 0
);

COMMIT;
