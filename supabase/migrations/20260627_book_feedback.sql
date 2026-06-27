-- Book feedback: users rate individual scriptures thumbs up/down.
-- Used by admin to prioritise corpus quality improvements.
-- One rating per user per scripture — upsert on conflict.

CREATE TABLE IF NOT EXISTS book_feedback (
  id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID        REFERENCES auth.users(id) ON DELETE CASCADE,
  scripture   TEXT        NOT NULL,
  rating      SMALLINT    NOT NULL CHECK (rating IN (1, -1)),
  note        TEXT,                          -- optional free-text (future)
  created_at  TIMESTAMPTZ DEFAULT now(),
  updated_at  TIMESTAMPTZ DEFAULT now(),
  UNIQUE (user_id, scripture)               -- one rating per user per book
);

-- Anonymous ratings allowed (user_id nullable for possible future use)
ALTER TABLE book_feedback ALTER COLUMN user_id DROP NOT NULL;

-- Index for admin aggregation query
CREATE INDEX IF NOT EXISTS idx_book_feedback_scripture ON book_feedback (scripture);
CREATE INDEX IF NOT EXISTS idx_book_feedback_user     ON book_feedback (user_id);

-- RLS: users can only see and modify their own ratings
ALTER TABLE book_feedback ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users read own book feedback"
  ON book_feedback FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users insert own book feedback"
  ON book_feedback FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users update own book feedback"
  ON book_feedback FOR UPDATE
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users delete own book feedback"
  ON book_feedback FOR DELETE
  USING (auth.uid() = user_id);
