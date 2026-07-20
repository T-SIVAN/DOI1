BEGIN;

-- The web role remains RLS-bound to app.current_user_id.  Only this NOLOGIN
-- worker group may see all deletion tombstones after a profile is removed.
-- Run this migration with a database administrator that has CREATEROLE.
DO $migration$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'research_cos_delete_worker'
    ) THEN
        CREATE ROLE research_cos_delete_worker
            NOLOGIN
            NOSUPERUSER
            NOCREATEDB
            NOCREATEROLE
            NOREPLICATION
            BYPASSRLS;
    END IF;
END
$migration$;

ALTER ROLE research_cos_delete_worker
    NOLOGIN
    NOSUPERUSER
    NOCREATEDB
    NOCREATEROLE
    NOREPLICATION
    BYPASSRLS;

REVOKE ALL ON TABLE cos_delete_outbox FROM research_cos_delete_worker;
GRANT USAGE ON SCHEMA public TO research_cos_delete_worker;
GRANT SELECT (id, object_key, attempts, claimed_until, processed_at)
    ON TABLE cos_delete_outbox TO research_cos_delete_worker;
GRANT UPDATE (attempts, claimed_until, last_error, processed_at)
    ON TABLE cos_delete_outbox TO research_cos_delete_worker;

COMMIT;

-- A database administrator must create the LOGIN role separately with a
-- generated secret, then grant only membership in the constrained group.
-- Keep this example aligned with deploy/COS_DELETE_WORKER.md and never put the
-- password in Git:
--   CREATE ROLE research_cos_delete_worker_login
--       LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION
--       PASSWORD '<generated-secret>';
--   GRANT research_cos_delete_worker TO research_cos_delete_worker_login;
--   REVOKE CREATE ON SCHEMA public FROM research_cos_delete_worker_login;
