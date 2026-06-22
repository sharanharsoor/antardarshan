-- ════════════════════════════════════════════════════════════════════
-- Migration: Conversation Persistence (2026-06-21)
-- Self-contained — creates tables if they don't exist, then adds columns.
-- Safe to re-run.
-- ════════════════════════════════════════════════════════════════════

-- 1. Create conversations table (if not already created by initial schema)
CREATE TABLE IF NOT EXISTS conversations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    title       TEXT,
    shared      BOOLEAN DEFAULT FALSE,
    share_slug  TEXT UNIQUE,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Add new columns if table already existed without them
ALTER TABLE conversations
    ADD COLUMN IF NOT EXISTS share_slug TEXT,
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

-- 2. Create messages table (if not already created by initial schema)
CREATE TABLE IF NOT EXISTS messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content         TEXT NOT NULL,
    citations       JSONB,
    mode            TEXT,
    model           TEXT,
    tokens_used     INTEGER,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Add new columns if table already existed without them
ALTER TABLE messages
    ADD COLUMN IF NOT EXISTS model TEXT,
    ADD COLUMN IF NOT EXISTS tokens_used INTEGER;

-- 3. RLS for conversations
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users read own conversations"   ON conversations;
DROP POLICY IF EXISTS "Users write own conversations"  ON conversations;
DROP POLICY IF EXISTS "Users update own conversations" ON conversations;
DROP POLICY IF EXISTS "Users delete own conversations" ON conversations;

CREATE POLICY "Users read own conversations"   ON conversations FOR SELECT
    USING (auth.uid() = user_id OR shared = TRUE);
CREATE POLICY "Users write own conversations"  ON conversations FOR INSERT
    WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users update own conversations" ON conversations FOR UPDATE
    USING (auth.uid() = user_id);
CREATE POLICY "Users delete own conversations" ON conversations FOR DELETE
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users read conversation messages" ON messages;
DROP POLICY IF EXISTS "Users write messages"             ON messages;

CREATE POLICY "Users read conversation messages" ON messages FOR SELECT
    USING (EXISTS (
        SELECT 1 FROM conversations c
        WHERE c.id = messages.conversation_id
        AND (c.user_id = auth.uid() OR c.shared = TRUE)
    ));
CREATE POLICY "Users write messages" ON messages FOR INSERT
    WITH CHECK (EXISTS (
        SELECT 1 FROM conversations c
        WHERE c.id = messages.conversation_id AND c.user_id = auth.uid()
    ));

-- 4. Per-user query tracking (50 queries/day limit)
CREATE TABLE IF NOT EXISTS user_query_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,
    mode            TEXT,
    model           TEXT,
    queried_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_query_log_daily
    ON user_query_log(user_id, queried_at);

ALTER TABLE user_query_log ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users see own query log" ON user_query_log;
CREATE POLICY "Users see own query log"
    ON user_query_log FOR SELECT USING (auth.uid() = user_id);

-- 5. Auto-update conversations.updated_at when a message is added
CREATE OR REPLACE FUNCTION update_conversation_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE conversations SET updated_at = NOW() WHERE id = NEW.conversation_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS on_message_insert ON messages;
CREATE TRIGGER on_message_insert
    AFTER INSERT ON messages
    FOR EACH ROW EXECUTE FUNCTION update_conversation_timestamp();

-- 6. Indexes
CREATE INDEX IF NOT EXISTS idx_conversations_user_updated
    ON conversations(user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_conv
    ON messages(conversation_id, created_at);

-- Verify
SELECT 'Migration complete' AS status,
       COUNT(*) AS conversation_count FROM conversations;
