BEGIN;

-- Durable tombstones bridge PostgreSQL transactions and non-transactional COS.
-- Deliberately no FK to profiles: "delete all data" must retain pending deletes
-- even after the application profile has been removed.
CREATE TABLE IF NOT EXISTS cos_delete_outbox (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id text NOT NULL,
    object_key text NOT NULL UNIQUE,
    attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    claimed_until timestamptz,
    last_error text NOT NULL DEFAULT '',
    processed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS cos_delete_outbox_pending_idx
    ON cos_delete_outbox (id)
    WHERE processed_at IS NULL;

ALTER TABLE cos_delete_outbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE cos_delete_outbox FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS cos_delete_outbox_owner ON cos_delete_outbox;
CREATE POLICY cos_delete_outbox_owner ON cos_delete_outbox
    FOR ALL
    USING (user_id = current_setting('app.current_user_id', true))
    WITH CHECK (user_id = current_setting('app.current_user_id', true));

COMMIT;
