/**
 * Supabase helpers for reader features: bookmarks, reading progress, highlights.
 * All calls are client-side (browser) — uses the anon key with RLS.
 * Every function is wrapped in try-catch so network failures resolve silently
 * rather than throwing unhandled rejections that pollute the browser console.
 */
import { createClient } from "@/utils/supabase/client";

// ── Reading progress ─────────────────────────────────────────────────────────

export async function saveProgress(slug: string, chapter: number, verse: number) {
  try {
    const supabase = createClient();
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return;
    await supabase.from("reading_progress").upsert({
      user_id: user.id, slug, chapter, verse,
      updated_at: new Date().toISOString(),
    }, { onConflict: "user_id,slug" });
  } catch { /* silent — non-critical */ }
}

export async function getProgress(slug: string): Promise<{ chapter: number; verse: number } | null> {
  try {
    const supabase = createClient();
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return null;
    const { data } = await supabase
      .from("reading_progress").select("chapter, verse")
      .eq("user_id", user.id).eq("slug", slug).single();
    return data ?? null;
  } catch { return null; }
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
  try {
    const supabase = createClient();
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return null;
    const { data, error } = await supabase
      .from("bookmarks")
      .upsert({ user_id: user.id, slug, scripture, chapter, verse, note: note ?? null },
        { onConflict: "user_id,slug,chapter,verse" })
      .select("id").single();
    if (error) return null;
    return data?.id ?? null;
  } catch { return null; }
}

export async function removeBookmark(id: string): Promise<boolean> {
  try {
    const supabase = createClient();
    const { error } = await supabase.from("bookmarks").delete().eq("id", id);
    return !error;
  } catch { return false; }
}

export async function getBookmarksForSlug(slug: string): Promise<Bookmark[]> {
  try {
    const supabase = createClient();
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return [];
    const { data } = await supabase
      .from("bookmarks").select("*")
      .eq("user_id", user.id).eq("slug", slug)
      .order("created_at", { ascending: false });
    return data ?? [];
  } catch { return []; }
}

export async function isVerseBookmarked(
  slug: string, chapter: number, verse: number
): Promise<string | null> {
  try {
    const supabase = createClient();
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return null;
    const { data } = await supabase
      .from("bookmarks").select("id")
      .eq("user_id", user.id).eq("slug", slug)
      .eq("chapter", chapter).eq("verse", verse).single();
    return data?.id ?? null;
  } catch { return null; }
}

// ── Highlights + Notes ───────────────────────────────────────────────────────

export interface Highlight {
  id: string;
  slug: string;
  chapter: number;
  verse: number;
  selected_text: string;
  selected_occurrence: number;
  color: 'yellow' | 'green' | 'blue' | 'pink';
  note: string | null;
  created_at: string;
}

export async function getCurrentUserId(): Promise<string | null> {
  try {
    const supabase = createClient();
    const { data: { session } } = await supabase.auth.getSession();
    return session?.user?.id ?? null;
  } catch { return null; }
}

export async function getHighlightsForChapter(slug: string, chapter: number): Promise<Highlight[]> {
  try {
    const supabase = createClient();
    const { data: { session } } = await supabase.auth.getSession();
    if (!session?.user) return [];
    const { data } = await supabase
      .from('highlights').select('*')
      .eq('user_id', session.user.id).eq('slug', slug).eq('chapter', chapter)
      .order('created_at', { ascending: true });
    return (data ?? []) as Highlight[];
  } catch { return []; }
}

export async function saveHighlight(
  slug: string, chapter: number, verse: number,
  selectedText: string, selectedOccurrence: number,
  color: Highlight['color'],
): Promise<Highlight | null> {
  try {
    const supabase = createClient();
    // getUser() (not getSession()) initializes the JWT in this client instance
    // so RLS auth.uid() resolves correctly on INSERT
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return null;
    const { data, error } = await supabase
      .from('highlights')
      .insert({ user_id: user.id, slug, chapter, verse,
        selected_text: selectedText, selected_occurrence: selectedOccurrence, color })
      .select().single();
    if (error) return null;
    return data as Highlight;
  } catch { return null; }
}

export async function updateHighlightColor(id: string, color: Highlight['color']): Promise<boolean> {
  try {
    const supabase = createClient();
    const { error } = await supabase.from('highlights').update({ color }).eq('id', id);
    return !error;
  } catch { return false; }
}

export async function deleteHighlight(id: string): Promise<boolean> {
  try {
    const supabase = createClient();
    const { error } = await supabase.from('highlights').delete().eq('id', id);
    return !error;
  } catch { return false; }
}

export async function updateHighlightNote(id: string, note: string): Promise<boolean> {
  try {
    const supabase = createClient();
    const { error } = await supabase
      .from('highlights')
      .update({ note: note || null, updated_at: new Date().toISOString() })
      .eq('id', id);
    return !error;
  } catch { return false; }
}

// ── Auth helper ──────────────────────────────────────────────────────────────

export async function getCurrentUser() {
  try {
    const supabase = createClient();
    const { data: { user } } = await supabase.auth.getUser();
    return user;
  } catch { return null; }
}
