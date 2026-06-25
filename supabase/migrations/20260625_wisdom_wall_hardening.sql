-- ════════════════════════════════════════════════════════════════════
-- Migration: Wisdom Wall hardening (2026-06-25)
-- 1. UNIQUE constraint on display_name (prevents impersonation)
-- 2. Auth guard in cast_wisdom_vote RPC (blocks client-side manipulation)
-- Safe to re-run.
-- ════════════════════════════════════════════════════════════════════

-- Display name must be globally unique to prevent impersonation.
-- Guard: resolve existing duplicates before adding the unique constraint.
-- Older duplicates (rn > 1) get a suffix derived from their user_id (first 8 chars).
-- Using user_id avoids collision with pre-existing names like "Sage_2".
-- e.g. duplicate "Sage" rows → "Sage" (newest), "Sage_a3f8c1d2" (older)
WITH ranked AS (
    SELECT user_id,
           display_name,
           ROW_NUMBER() OVER (
               PARTITION BY display_name
               ORDER BY updated_at DESC     -- most recent keeps original name
           ) AS rn
    FROM user_profiles
)
UPDATE user_profiles AS up
SET    display_name = up.display_name || '_' || LEFT(up.user_id::TEXT, 8)
FROM   ranked AS r
WHERE  up.user_id = r.user_id
  AND  r.rn > 1;  -- only older duplicates get the suffix

ALTER TABLE user_profiles
    DROP CONSTRAINT IF EXISTS user_profiles_display_name_unique;
ALTER TABLE user_profiles
    ADD CONSTRAINT user_profiles_display_name_unique UNIQUE (display_name);

-- ── Hardened vote RPC with auth guard ────────────────────────────────
-- When called from the browser (anon key), auth.uid() is set.
-- When called server-side with service-role key, auth.uid() is NULL.
-- The guard allows service-role calls but blocks client-side impersonation.

CREATE OR REPLACE FUNCTION cast_wisdom_vote(
    p_post_id  UUID,
    p_user_id  UUID,
    p_vote     TEXT   -- 'up' or 'down'
) RETURNS TEXT LANGUAGE plpgsql SECURITY INVOKER AS $$
DECLARE
    v_existing TEXT;
BEGIN
    -- Prevent client-side vote manipulation: caller must match authenticated user
    IF auth.uid() IS NOT NULL AND p_user_id != auth.uid() THEN
        RAISE EXCEPTION 'Unauthorized: user_id does not match authenticated user';
    END IF;

    IF p_vote NOT IN ('up', 'down') THEN
        RAISE EXCEPTION 'Invalid vote type: must be ''up'' or ''down''';
    END IF;

    SELECT vote_type INTO v_existing
    FROM wisdom_votes
    WHERE post_id = p_post_id AND user_id = p_user_id;

    IF v_existing IS NULL THEN
        INSERT INTO wisdom_votes (post_id, user_id, vote_type)
        VALUES (p_post_id, p_user_id, p_vote);

        IF p_vote = 'up' THEN
            UPDATE wisdom_posts SET upvotes   = upvotes   + 1 WHERE id = p_post_id;
        ELSE
            UPDATE wisdom_posts SET downvotes = downvotes + 1 WHERE id = p_post_id;
        END IF;
        RETURN 'added';

    ELSIF v_existing = p_vote THEN
        DELETE FROM wisdom_votes WHERE post_id = p_post_id AND user_id = p_user_id;
        IF p_vote = 'up' THEN
            UPDATE wisdom_posts SET upvotes   = GREATEST(upvotes   - 1, 0) WHERE id = p_post_id;
        ELSE
            UPDATE wisdom_posts SET downvotes = GREATEST(downvotes - 1, 0) WHERE id = p_post_id;
        END IF;
        RETURN 'removed';

    ELSE
        UPDATE wisdom_votes SET vote_type = p_vote
        WHERE post_id = p_post_id AND user_id = p_user_id;
        IF p_vote = 'up' THEN
            UPDATE wisdom_posts SET upvotes   = upvotes   + 1,
                                    downvotes = GREATEST(downvotes - 1, 0) WHERE id = p_post_id;
        ELSE
            UPDATE wisdom_posts SET downvotes = downvotes + 1,
                                    upvotes   = GREATEST(upvotes   - 1, 0) WHERE id = p_post_id;
        END IF;
        RETURN 'changed';
    END IF;
END;
$$;

-- Handle display name collision in set_display_name endpoint
-- (backend catches the unique violation and returns a friendly 409 error)

SELECT 'Wisdom Wall hardening applied' AS status;
