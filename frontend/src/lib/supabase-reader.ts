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

// ── Highlights + Notes ───────────────────────────────────────────────────────

export interface Highlight {
  id: string;
  slug: string;
  chapter: number;
  verse: number;
  selected_text: string;
  selected_occurrence: number;
  normalized_text_hash: string | null;
  color: 'yellow' | 'green' | 'blue' | 'pink';
  note: string | null;
  created_at: string;
}

export async function getHighlightsForChapter(slug: string, chapter: number): Promise<Highlight[]> {
  const supabase = createClient();
  const { data: { session } } = await supabase.auth.getSession();
  const user = session?.user;
  if (!user) return [];

  const { data } = await supabase
    .from('highlights')
    .select('*')
    .eq('user_id', user.id)
    .eq('slug', slug)
    .eq('chapter', chapter)
    .order('created_at', { ascending: true });

  return (data ?? []) as Highlight[];
}

export async function saveHighlight(
  slug: string,
  chapter: number,
  verse: number,
  selectedText: string,
  selectedOccurrence: number,
  normalizedTextHash: string,
  color: Highlight['color'],
): Promise<Highlight | null> {
  const supabase = createClient();
  const { data: { session } } = await supabase.auth.getSession();
  const user = session?.user;
  if (!user) return null;

  const { data, error } = await supabase
    .from('highlights')
    .insert({
      user_id: user.id,
      slug,
      chapter,
      verse,
      selected_text: selectedText,
      selected_occurrence: selectedOccurrence,
      normalized_text_hash: normalizedTextHash,
      color,
    })
    .select()
    .single();

  if (error) return null;
  return data as Highlight;
}

export async function deleteHighlight(id: string): Promise<boolean> {
  const supabase = createClient();
  const { error } = await supabase.from('highlights').delete().eq('id', id);
  return !error;
}

export async function updateHighlightNote(id: string, note: string): Promise<boolean> {
  const supabase = createClient();
  const { error } = await supabase
    .from('highlights')
    .update({ note: note || null, updated_at: new Date().toISOString() })
    .eq('id', id);
  return !error;
}

// ── Auth helper ──────────────────────────────────────────────────────────────

export async function getCurrentUser() {
  const supabase = createClient();
  const { data: { user } } = await supabase.auth.getUser();
  return user;
}
