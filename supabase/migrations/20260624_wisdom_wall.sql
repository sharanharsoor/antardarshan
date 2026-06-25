-- ════════════════════════════════════════════════════════════════════
-- Migration: Wisdom Wall (2026-06-24)
-- Tables: user_profiles, wisdom_posts, wisdom_votes, wisdom_mod_attempts
-- Safe to re-run (CREATE TABLE IF NOT EXISTS throughout).
-- ════════════════════════════════════════════════════════════════════

-- User display names for Wisdom Wall (one per account)
CREATE TABLE IF NOT EXISTS user_profiles (
    user_id      UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    display_name TEXT NOT NULL,
    updated_at   TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Users manage own profile" ON user_profiles;
DROP POLICY IF EXISTS "Public can read profiles" ON user_profiles;
CREATE POLICY "Users manage own profile" ON user_profiles
    FOR ALL USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Public can read profiles" ON user_profiles
    FOR SELECT USING (true);

-- ── Wisdom posts ──────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS wisdom_posts (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id            UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
    display_name       TEXT NOT NULL,        -- snapshot at post time
    content            TEXT NOT NULL,        -- max 2000 chars enforced in app
    contact_email      TEXT,                 -- optional; hidden after 15 days
    contact_phone      TEXT,                 -- optional; hidden after 15 days
    contact_hidden_at  TIMESTAMPTZ,          -- set by cron when > 15 days old
    upvotes            INTEGER DEFAULT 0 NOT NULL,
    downvotes          INTEGER DEFAULT 0 NOT NULL,
    is_removed         BOOLEAN DEFAULT FALSE NOT NULL,
    is_edited          BOOLEAN DEFAULT FALSE NOT NULL,
    moderation_status  TEXT DEFAULT 'approved'
                           CHECK (moderation_status IN ('pending', 'approved', 'rejected')),
    created_at         TIMESTAMPTZ DEFAULT NOW(),
    updated_at         TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_wisdom_posts_feed
    ON wisdom_posts(created_at DESC)
    WHERE is_removed = FALSE AND moderation_status = 'approved';

CREATE INDEX IF NOT EXISTS idx_wisdom_posts_user
    ON wisdom_posts(user_id, created_at DESC);

ALTER TABLE wisdom_posts ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Public can read approved posts" ON wisdom_posts;
DROP POLICY IF EXISTS "Users manage own posts"        ON wisdom_posts;
CREATE POLICY "Public can read approved posts" ON wisdom_posts
    FOR SELECT USING (is_removed = FALSE AND moderation_status = 'approved');
CREATE POLICY "Users manage own posts" ON wisdom_posts
    FOR ALL USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- ── Votes ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS wisdom_votes (
    post_id    UUID REFERENCES wisdom_posts(id) ON DELETE CASCADE,
    user_id    UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    vote_type  TEXT NOT NULL CHECK (vote_type IN ('up', 'down')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (post_id, user_id)
);

ALTER TABLE wisdom_votes ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Users manage own votes"  ON wisdom_votes;
DROP POLICY IF EXISTS "Public can read votes"   ON wisdom_votes;
CREATE POLICY "Users manage own votes" ON wisdom_votes
    FOR ALL USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Public can read votes" ON wisdom_votes
    FOR SELECT USING (true);

-- ── Moderation attempt tracking ───────────────────────────────────────
-- One row per (user, date); attempts incremented per LLM call.
-- Enforces 5-attempt-per-day limit regardless of approval/rejection.

CREATE TABLE IF NOT EXISTS wisdom_mod_attempts (
    user_id      UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    attempt_date DATE NOT NULL DEFAULT CURRENT_DATE,
    attempts     INTEGER DEFAULT 1 NOT NULL,
    PRIMARY KEY (user_id, attempt_date)
);

ALTER TABLE wisdom_mod_attempts ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Users see own attempts" ON wisdom_mod_attempts;
CREATE POLICY "Users see own attempts" ON wisdom_mod_attempts
    FOR ALL USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- ── RPC: atomic increment of moderation attempts ─────────────────────
CREATE OR REPLACE FUNCTION increment_wisdom_mod_attempts(
    p_user_id UUID,
    p_date    DATE
) RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO wisdom_mod_attempts (user_id, attempt_date, attempts)
    VALUES (p_user_id, p_date, 1)
    ON CONFLICT (user_id, attempt_date)
    DO UPDATE SET attempts = wisdom_mod_attempts.attempts + 1;
END;
$$;

-- ── RPC: atomic vote update ───────────────────────────────────────────
-- Upserts a vote and adjusts the denormalised upvotes/downvotes counters.
CREATE OR REPLACE FUNCTION cast_wisdom_vote(
    p_post_id  UUID,
    p_user_id  UUID,
    p_vote     TEXT   -- 'up' or 'down'
) RETURNS TEXT LANGUAGE plpgsql AS $$
DECLARE
    v_existing TEXT;
BEGIN
    SELECT vote_type INTO v_existing
    FROM wisdom_votes
    WHERE post_id = p_post_id AND user_id = p_user_id;

    IF v_existing IS NULL THEN
        -- New vote
        INSERT INTO wisdom_votes (post_id, user_id, vote_type)
        VALUES (p_post_id, p_user_id, p_vote);

        IF p_vote = 'up' THEN
            UPDATE wisdom_posts SET upvotes   = upvotes   + 1 WHERE id = p_post_id;
        ELSE
            UPDATE wisdom_posts SET downvotes = downvotes + 1 WHERE id = p_post_id;
        END IF;
        RETURN 'added';

    ELSIF v_existing = p_vote THEN
        -- Remove vote (toggle off)
        DELETE FROM wisdom_votes WHERE post_id = p_post_id AND user_id = p_user_id;
        IF p_vote = 'up' THEN
            UPDATE wisdom_posts SET upvotes   = GREATEST(upvotes   - 1, 0) WHERE id = p_post_id;
        ELSE
            UPDATE wisdom_posts SET downvotes = GREATEST(downvotes - 1, 0) WHERE id = p_post_id;
        END IF;
        RETURN 'removed';

    ELSE
        -- Change vote direction
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

SELECT 'Wisdom Wall schema ready' AS status;
