-- ════════════════════════════════════════════════════════════════════
-- Migration: Highlights + Notes (2026-06-22, revised 2026-06-23)
-- NON-DESTRUCTIVE — safe to re-run on any environment with existing data.
-- Uses CREATE TABLE IF NOT EXISTS + ADD COLUMN IF NOT EXISTS so user
-- highlight data is never dropped.
-- ════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS highlights (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    slug                TEXT NOT NULL,
    chapter             INTEGER NOT NULL,
    verse               INTEGER NOT NULL,
    selected_text       TEXT NOT NULL,
    selected_occurrence INTEGER NOT NULL DEFAULT 0,
    color               TEXT NOT NULL DEFAULT 'yellow'
                            CHECK (color IN ('yellow', 'green', 'blue', 'pink')),
    note                TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

-- Add any columns that may be missing from older installs
ALTER TABLE highlights ADD COLUMN IF NOT EXISTS selected_occurrence INTEGER NOT NULL DEFAULT 0;
ALTER TABLE highlights ADD COLUMN IF NOT EXISTS note TEXT;

CREATE INDEX IF NOT EXISTS idx_highlights_reading
    ON highlights(user_id, slug, chapter);

ALTER TABLE highlights ENABLE ROW LEVEL SECURITY;

-- Recreate policy cleanly (DROP IF EXISTS is safe — no data loss)
DROP POLICY IF EXISTS "Users manage own highlights" ON highlights;
CREATE POLICY "Users manage own highlights" ON highlights
    FOR ALL USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

SELECT 'highlights table ready' AS status;
