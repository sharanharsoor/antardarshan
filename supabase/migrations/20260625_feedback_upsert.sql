-- ════════════════════════════════════════════════════════════════════
-- Migration: feedback_responses unique constraint (2026-06-25)
-- Ensures one rating per (user, message) — enables safe upsert.
-- Safe to re-run.
-- ════════════════════════════════════════════════════════════════════

-- Deduplicate first: keep only the latest row per (user_id, message_id)
WITH ranked AS (
    SELECT id,
           ROW_NUMBER() OVER (
               PARTITION BY user_id, message_id
               ORDER BY created_at DESC   -- keep most recent
           ) AS rn
    FROM feedback_responses
    WHERE message_id IS NOT NULL
)
DELETE FROM feedback_responses
WHERE id IN (SELECT id FROM ranked WHERE rn > 1);

-- Add unique constraint (partial: only rows where message_id is not null)
ALTER TABLE feedback_responses
    DROP CONSTRAINT IF EXISTS feedback_responses_user_message_unique;
ALTER TABLE feedback_responses
    ADD CONSTRAINT feedback_responses_user_message_unique
    UNIQUE (user_id, message_id);

SELECT 'feedback_responses unique constraint applied' AS status;
