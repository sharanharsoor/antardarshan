-- Migration: Bookmark uniqueness constraint (2026-06-21)
-- Safe to re-run: drops and recreates constraint if it already exists.

ALTER TABLE bookmarks
    DROP CONSTRAINT IF EXISTS bookmarks_user_verse_unique;

ALTER TABLE bookmarks
    ADD CONSTRAINT bookmarks_user_verse_unique
    UNIQUE (user_id, slug, chapter, verse);
