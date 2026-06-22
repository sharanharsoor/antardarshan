-- ════════════════════════════════════════════════════════════════════
-- Migration: Remaining schema tables (2026-06-21)
-- Creates feedback, issue report, and leaderboard tables.
-- Safe to re-run (all use CREATE TABLE IF NOT EXISTS).
-- ════════════════════════════════════════════════════════════════════

-- Feedback on AI Q&A responses (thumbs up/down)
CREATE TABLE IF NOT EXISTS feedback_responses (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    message_id      UUID REFERENCES messages(id) ON DELETE CASCADE,
    rating          SMALLINT NOT NULL CHECK (rating IN (-1, 1)),
    comment         TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Feedback on books/scriptures in the reading library
CREATE TABLE IF NOT EXISTS feedback_books (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    slug        TEXT NOT NULL,
    scripture   TEXT NOT NULL,
    rating      SMALLINT NOT NULL CHECK (rating IN (-1, 1)),
    comment     TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, slug)
);

-- Issue reports on specific verses (OCR errors, wrong content, etc.)
CREATE TABLE IF NOT EXISTS issue_reports (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    slug        TEXT NOT NULL,
    scripture   TEXT NOT NULL,
    chapter     INTEGER,
    verse       INTEGER,
    issue_type  TEXT NOT NULL CHECK (issue_type IN (
        'ocr_garbage', 'wrong_content', 'missing_text', 'formatting', 'offensive', 'other'
    )),
    comment     TEXT,
    status      TEXT DEFAULT 'open' CHECK (status IN ('open', 'acknowledged', 'fixed', 'wontfix')),
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Leaderboard opt-in (Tier 3 feature)
CREATE TABLE IF NOT EXISTS leaderboard_settings (
    user_id         UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    opted_in        BOOLEAN DEFAULT FALSE,
    display_name    TEXT,
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- RLS
ALTER TABLE feedback_responses  ENABLE ROW LEVEL SECURITY;
ALTER TABLE feedback_books      ENABLE ROW LEVEL SECURITY;
ALTER TABLE issue_reports       ENABLE ROW LEVEL SECURITY;
ALTER TABLE leaderboard_settings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users manage own response feedback"  ON feedback_responses;
DROP POLICY IF EXISTS "Users manage own book feedback"     ON feedback_books;
DROP POLICY IF EXISTS "Users manage own issue reports"     ON issue_reports;
DROP POLICY IF EXISTS "Users manage own leaderboard settings" ON leaderboard_settings;

CREATE POLICY "Users manage own response feedback" ON feedback_responses
    FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "Users manage own book feedback" ON feedback_books
    FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "Users manage own issue reports" ON issue_reports
    FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "Users manage own leaderboard settings" ON leaderboard_settings
    FOR ALL USING (auth.uid() = user_id);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_feedback_resp_user   ON feedback_responses(user_id);
CREATE INDEX IF NOT EXISTS idx_feedback_books_slug  ON feedback_books(slug);
CREATE INDEX IF NOT EXISTS idx_issue_reports_slug   ON issue_reports(slug, status);

SELECT 'Schema complete' AS status,
    (SELECT COUNT(*) FROM information_schema.tables
     WHERE table_schema = 'public') AS total_tables;
