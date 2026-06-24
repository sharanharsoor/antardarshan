/**
 * Conversation persistence — Supabase client-side calls.
 *
 * Architecture:
 * - Conversation CRUD: direct Supabase client (RLS-protected, user-scoped)
 * - Message reads: direct Supabase client
 * - Message writes: via backend /api/query (service key, writes after LLM)
 * - Quota reads: via backend /api/quota-status/user
 */

import { createClient } from "@/utils/supabase/client";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ── Types ─────────────────────────────────────────────────────────────────────

export interface Conversation {
  id: string;
  user_id: string | null;
  title: string | null;
  shared: boolean;
  created_at: string;
  updated_at: string;
}

export interface ConversationMessage {
  id: string;
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
  citations: Array<{ scripture: string; chapter: number; verse: number; translator: string }> | null;
  mode: string | null;
  model: string | null;
  tokens_used: number | null;
  created_at: string;
}

export interface UserQuotaStatus {
  per_user_used: number;
  per_user_limit: number;
  per_user_remaining: number;
  per_user_allowed: boolean;
}

// ── Conversation CRUD ──────────────────────────────────────────────────────────

export async function createConversation(): Promise<Conversation | null> {
  const supabase = createClient();
  const { data: { user } } = await supabase.auth.getUser();

  const { data, error } = await supabase
    .from("conversations")
    .insert({ user_id: user?.id ?? null, shared: false })
    .select()
    .single();

  if (error) {
    console.error("createConversation error:", error.message);
    return null;
  }
  return data as Conversation;
}

export async function listConversations(limit = 30): Promise<Conversation[]> {
  const supabase = createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return [];

  const { data, error } = await supabase
    .from("conversations")
    .select("id, title, shared, created_at, updated_at")
    .eq("user_id", user.id)
    .order("updated_at", { ascending: false })
    .limit(limit);

  if (error) return [];
  return (data ?? []) as Conversation[];
}

export async function loadConversation(
  conversationId: string
): Promise<{ conversation: Conversation; messages: ConversationMessage[] } | null> {
  // Send Authorization header so the backend can authenticate the owner.
  // Shared conversations are readable without auth — the header is optional
  // but required for private (owner-only) conversations.
  const supabase = createClient();
  const { data: { session } } = await supabase.auth.getSession();
  const headers: Record<string, string> = {};
  if (session?.access_token) {
    headers["Authorization"] = `Bearer ${session.access_token}`;
  }

  const res = await fetch(`${API_BASE}/api/conversations/${conversationId}`, { headers });
  if (!res.ok) return null;
  return res.json();
}

export async function shareConversation(conversationId: string): Promise<string | null> {
  const supabase = createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return null;

  const { error } = await supabase
    .from("conversations")
    .update({ shared: true })
    .eq("id", conversationId)
    .eq("user_id", user.id);

  if (error) return null;

  return `${window.location.origin}/ask/c/${conversationId}`;
}

export async function unshareConversation(conversationId: string): Promise<boolean> {
  const supabase = createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return false;

  const { error } = await supabase
    .from("conversations")
    .update({ shared: false })
    .eq("id", conversationId)
    .eq("user_id", user.id);

  return !error;
}

export async function renameConversation(conversationId: string, title: string): Promise<boolean> {
  const supabase = createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return false;

  const { error } = await supabase
    .from("conversations")
    .update({ title: title.trim().slice(0, 100) })
    .eq("id", conversationId)
    .eq("user_id", user.id);

  return !error;
}

export async function deleteConversation(conversationId: string): Promise<boolean> {
  const supabase = createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return false;

  const { error } = await supabase
    .from("conversations")
    .delete()
    .eq("id", conversationId)
    .eq("user_id", user.id);

  return !error;
}

// ── Query log ──────────────────────────────────────────────────────────────────

/** Delete all query-log entries for the current user (metadata only, no content). */
export async function clearQueryLog(): Promise<boolean> {
  const supabase = createClient();
  const { data: { session } } = await supabase.auth.getSession();
  if (!session?.access_token) return false;
  try {
    const res = await fetch(`${API_BASE}/api/query-log`, {
      method: "DELETE",
      headers: { "Authorization": `Bearer ${session.access_token}` },
    });
    return res.ok;
  } catch { return false; }
}

// ── Per-user quota ─────────────────────────────────────────────────────────────

export async function getUserQuota(): Promise<UserQuotaStatus | null> {
  // user_id is derived server-side from the JWT — send Authorization header
  const supabase = createClient();
  const { data: { session } } = await supabase.auth.getSession();
  if (!session?.access_token) return null;
  try {
    const res = await fetch(`${API_BASE}/api/quota-status/user`, {
      headers: { "Authorization": `Bearer ${session.access_token}` },
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

// ── Helpers ────────────────────────────────────────────────────────────────────

/**
 * Group conversations by recency for sidebar display.
 * Returns { today: [], yesterday: [], thisWeek: [], older: [] }
 */
export function groupConversationsByDate(conversations: Conversation[]) {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today.getTime() - 86400000);
  const weekAgo = new Date(today.getTime() - 7 * 86400000);

  return {
    today: conversations.filter(c => new Date(c.updated_at) >= today),
    yesterday: conversations.filter(c => {
      const d = new Date(c.updated_at);
      return d >= yesterday && d < today;
    }),
    thisWeek: conversations.filter(c => {
      const d = new Date(c.updated_at);
      return d >= weekAgo && d < yesterday;
    }),
    older: conversations.filter(c => new Date(c.updated_at) < weekAgo),
  };
}
