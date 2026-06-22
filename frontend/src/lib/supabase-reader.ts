/**
 * Supabase helpers for reader features: bookmarks + reading progress.
 * All calls are client-side (browser) — uses the anon key with RLS.
 */
import { createClient } from "@/utils/supabase/client";

// ── Reading progress ────────────────────────────────────────────────────────

export async function saveProgress(slug: string, chapter: number, verse: number) {
  const supabase = createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return;

  await supabase.from("reading_progress").upsert({
    user_id: user.id,
    slug,
    chapter,
    verse,
    updated_at: new Date().toISOString(),
  }, { onConflict: "user_id,slug" });
}

export async function getProgress(slug: string): Promise<{ chapter: number; verse: number } | null> {
  const supabase = createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return null;

  const { data } = await supabase
    .from("reading_progress")
    .select("chapter, verse")
    .eq("user_id", user.id)
    .eq("slug", slug)
    .single();

  return data ?? null;
}

// ── Bookmarks ────────────────────────────────────────────────────────────────

export interface Bookmark {
  id: string;
  slug: string;
  scripture: string;
  chapter: number;
  verse: number;
  note: string | null;
  created_at: string;
}

export async function addBookmark(
  slug: string, scripture: string, chapter: number, verse: number, note?: string
): Promise<string | null> {
  const supabase = createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return null;

  const { data, error } = await supabase
    .from("bookmarks")
    .upsert({
      user_id: user.id,
      slug,
      scripture,
      chapter,
      verse,
      note: note ?? null,
    }, { onConflict: "user_id,slug,chapter,verse" })
    .select("id")
    .single();
  if (error) return null;
  return data?.id ?? null;
}

export async function removeBookmark(id: string): Promise<boolean> {
  const supabase = createClient();
  const { error } = await supabase.from("bookmarks").delete().eq("id", id);
  return !error;
}

export async function getBookmarksForSlug(slug: string): Promise<Bookmark[]> {
  const supabase = createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return [];

  const { data } = await supabase
    .from("bookmarks")
    .select("*")
    .eq("user_id", user.id)
    .eq("slug", slug)
    .order("created_at", { ascending: false });

  return data ?? [];
}

export async function isVerseBookmarked(
  slug: string, chapter: number, verse: number
): Promise<string | null> {
  const supabase = createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return null;

  const { data } = await supabase
    .from("bookmarks")
    .select("id")
    .eq("user_id", user.id)
    .eq("slug", slug)
    .eq("chapter", chapter)
    .eq("verse", verse)
    .single();

  return data?.id ?? null;
}

// ── Auth helper ──────────────────────────────────────────────────────────────

export async function getCurrentUser() {
  const supabase = createClient();
  const { data: { user } } = await supabase.auth.getUser();
  return user;
}
