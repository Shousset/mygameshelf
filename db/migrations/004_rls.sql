-- Migration 004b — Row-Level Security on the user-owned content tables.
--
-- Defense-in-depth for multi-tenancy. The app already filters every query by
-- user_id (db/models.py); RLS is the safety net that makes the DATABASE refuse
-- to return another tenant's rows even if a future query forgets the filter.
--
-- Mechanism: the API connects as app_web (NOBYPASSRLS) and sets the session GUC
-- app.current_user_id on every connection checkout (db/connection.py). The
-- policy below only exposes rows whose user_id matches that GUC. If the GUC is
-- unset or empty (unauthenticated request, or a forgotten context), it resolves
-- to NULL and the policy matches NOTHING — deny by default.
--
-- SCOPE: only the 5 tables holding sensitive per-user content. user_profiles is
-- intentionally left out (the scheduler enumerates all users via
-- list_users_with_steam, and it only holds user_id + steam_id); sync_jobs,
-- steam_app_cache and steam_api_usage are operational/global tables. Those rely
-- on the existing app-level user_id filtering.
--
-- RUN AS THE TABLE OWNER OR A SUPERUSER (e.g. postgres). Idempotent.
--
--   psql "$DATABASE_URL" -f db/migrations/004_rls.sql

BEGIN;

DO $$
DECLARE
    t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['games', 'sessions', 'wishlist', 'achievements', 'sync_runs']
    LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY;', t);
        -- FORCE so the table owner is subject to RLS too (superusers still bypass).
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY;', t);
        EXECUTE format('DROP POLICY IF EXISTS tenant_isolation ON %I;', t);
        EXECUTE format($f$
            CREATE POLICY tenant_isolation ON %I
            USING      (user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid)
            WITH CHECK  (user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid);
        $f$, t);
    END LOOP;
END
$$;

COMMIT;
