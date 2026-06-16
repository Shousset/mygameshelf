-- Migration 004a — application Postgres roles for Row-Level Security.
--
-- RLS only does anything if the application connects as a NON-superuser role
-- (superusers and the table owner-with-BYPASSRLS always bypass RLS). So we use
-- two least-privilege login roles:
--
--   app_web    — the FastAPI API connects as this. NOBYPASSRLS, so the RLS
--                policies in 004_rls.sql are enforced. It sets the session GUC
--                app.current_user_id per request (see db/connection.py) and can
--                only see/modify the current user's rows.
--   app_worker — the sync worker (worker.py) and any cross-user/admin job
--                connect as this. BYPASSRLS, because it legitimately operates
--                across all users (claims jobs, lists users, syncs anyone's
--                games). It still relies on the explicit user_id filters in
--                db/models.py for correctness.
--
-- RUN THIS AS A SUPERUSER (e.g. postgres), once per database. Replace the
-- placeholder passwords first:
--
--   psql "$DATABASE_URL" -f db/migrations/004_roles.sql
--
-- Then point each process at its role via env:
--   API    : DB_USER=app_web     DB_PASSWORD=...
--   worker : DB_USER=app_worker  DB_PASSWORD=...
-- (In local dev you can keep DB_USER=postgres; RLS will simply be dormant.)

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_web') THEN
        CREATE ROLE app_web LOGIN PASSWORD 'CHANGE_ME_web'
            NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_worker') THEN
        CREATE ROLE app_worker LOGIN PASSWORD 'CHANGE_ME_worker'
            NOSUPERUSER BYPASSRLS NOCREATEDB NOCREATEROLE;
    END IF;
END
$$;

-- Privileges on the current schema (adjust if you use a non-public schema).
GRANT USAGE ON SCHEMA public TO app_web, app_worker;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_web, app_worker;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_web, app_worker;

-- Make future tables/sequences inherit the same grants (so new migrations don't
-- require re-granting). Must be run by the role that will own those objects.
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_web, app_worker;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO app_web, app_worker;
