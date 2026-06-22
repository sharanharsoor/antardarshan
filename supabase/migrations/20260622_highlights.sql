-- ════════════════════════════════════════════════════════════════════
-- Migration: Highlights + Notes (2026-06-22)
-- Safe to re-run (CREATE TABLE IF NOT EXISTS, DROP POLICY IF EXISTS).
-- ════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS highlights (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id              UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    slug                 TEXT NOT NULL,
    chapter              INTEGER NOT NULL,
    verse                INTEGER NOT NULL,
    selected_text        TEXT NOT NULL,
    selected_occurrence  INTEGER DEFAULT 0,
    normalized_text_hash TEXT,          -- short hash to detect parser drift
    color                TEXT NOT NULL DEFAULT 'yellow'
                             CHECK (color IN ('yellow', 'green', 'blue', 'pink')),
    note                 TEXT,
    created_at           TIMESTAMPTZ DEFAULT NOW(),
    updated_at           TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_highlights_reading
    ON highlights(user_id, slug, chapter);

ALTER TABLE highlights ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users manage own highlights" ON highlights;
CREATE POLICY "Users manage own highlights" ON highlights
    FOR ALL USING (auth.uid() = user_id);

SELECT 'highlights table ready' AS status;
