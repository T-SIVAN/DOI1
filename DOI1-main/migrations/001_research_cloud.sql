BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS profiles (
    user_id text PRIMARY KEY,
    issuer text NOT NULL,
    subject text NOT NULL,
    email text NOT NULL,
    display_name text NOT NULL DEFAULT '',
    quota_bytes bigint NOT NULL DEFAULT 209715200 CHECK (quota_bytes >= 0),
    used_bytes bigint NOT NULL DEFAULT 0 CHECK (used_bytes >= 0 AND used_bytes <= quota_bytes),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (issuer, subject)
);

CREATE TABLE IF NOT EXISTS conversations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id text NOT NULL REFERENCES profiles(user_id) ON DELETE CASCADE,
    title text NOT NULL DEFAULT '新对话' CHECK (char_length(title) <= 120),
    rolling_summary text NOT NULL DEFAULT '',
    messages_since_summary integer NOT NULL DEFAULT 0 CHECK (messages_since_summary >= 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (id, user_id)
);

CREATE INDEX IF NOT EXISTS conversations_user_updated_idx
    ON conversations (user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS messages (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id text NOT NULL REFERENCES profiles(user_id) ON DELETE CASCADE,
    conversation_id uuid NOT NULL,
    role text NOT NULL CHECK (role IN ('user', 'assistant', 'system', 'tool')),
    content text NOT NULL DEFAULT '',
    tool_call jsonb,
    status text NOT NULL DEFAULT 'completed',
    idempotency_key text,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (id, conversation_id, user_id),
    FOREIGN KEY (conversation_id, user_id)
        REFERENCES conversations(id, user_id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS messages_idempotency_idx
    ON messages (conversation_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS messages_conversation_created_idx
    ON messages (conversation_id, created_at);

CREATE TABLE IF NOT EXISTS attachments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id text NOT NULL REFERENCES profiles(user_id) ON DELETE CASCADE,
    conversation_id uuid NOT NULL,
    filename text NOT NULL,
    content_type text NOT NULL,
    size_bytes bigint NOT NULL CHECK (size_bytes > 0),
    sha256 text NOT NULL CHECK (char_length(sha256) = 64),
    object_key text NOT NULL UNIQUE,
    parsed_text text NOT NULL DEFAULT '',
    summary text NOT NULL DEFAULT '',
    parse_status text NOT NULL DEFAULT 'pending',
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (conversation_id, user_id)
        REFERENCES conversations(id, user_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS attachments_conversation_created_idx
    ON attachments (conversation_id, created_at);

CREATE TABLE IF NOT EXISTS artifacts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id text NOT NULL REFERENCES profiles(user_id) ON DELETE CASCADE,
    conversation_id uuid NOT NULL,
    message_id uuid,
    kind text NOT NULL,
    filename text NOT NULL,
    content_type text NOT NULL,
    size_bytes bigint NOT NULL CHECK (size_bytes > 0),
    sha256 text NOT NULL CHECK (char_length(sha256) = 64),
    object_key text NOT NULL UNIQUE,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (conversation_id, user_id)
        REFERENCES conversations(id, user_id) ON DELETE CASCADE,
    FOREIGN KEY (message_id, conversation_id, user_id)
        REFERENCES messages(id, conversation_id, user_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS artifacts_conversation_created_idx
    ON artifacts (conversation_id, created_at);

ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE attachments ENABLE ROW LEVEL SECURITY;
ALTER TABLE artifacts ENABLE ROW LEVEL SECURITY;

ALTER TABLE profiles FORCE ROW LEVEL SECURITY;
ALTER TABLE conversations FORCE ROW LEVEL SECURITY;
ALTER TABLE messages FORCE ROW LEVEL SECURITY;
ALTER TABLE attachments FORCE ROW LEVEL SECURITY;
ALTER TABLE artifacts FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS profiles_owner ON profiles;
CREATE POLICY profiles_owner ON profiles
    FOR ALL
    USING (user_id = current_setting('app.current_user_id', true))
    WITH CHECK (user_id = current_setting('app.current_user_id', true));

DROP POLICY IF EXISTS conversations_owner ON conversations;
CREATE POLICY conversations_owner ON conversations
    FOR ALL
    USING (user_id = current_setting('app.current_user_id', true))
    WITH CHECK (user_id = current_setting('app.current_user_id', true));

DROP POLICY IF EXISTS messages_owner ON messages;
CREATE POLICY messages_owner ON messages
    FOR ALL
    USING (user_id = current_setting('app.current_user_id', true))
    WITH CHECK (user_id = current_setting('app.current_user_id', true));

DROP POLICY IF EXISTS attachments_owner ON attachments;
CREATE POLICY attachments_owner ON attachments
    FOR ALL
    USING (user_id = current_setting('app.current_user_id', true))
    WITH CHECK (user_id = current_setting('app.current_user_id', true));

DROP POLICY IF EXISTS artifacts_owner ON artifacts;
CREATE POLICY artifacts_owner ON artifacts
    FOR ALL
    USING (user_id = current_setting('app.current_user_id', true))
    WITH CHECK (user_id = current_setting('app.current_user_id', true));

COMMIT;
