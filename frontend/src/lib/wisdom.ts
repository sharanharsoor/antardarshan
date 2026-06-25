/**
 * Wisdom Wall API client helpers.
 */
import { createClient } from "@/utils/supabase/client";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface WisdomPost {
  id: string;
  display_name: string;
  content: string;
  contact_email: string | null;
  contact_phone: string | null;
  contact_hidden_at: string | null;
  upvotes: number;
  downvotes: number;
  is_edited: boolean;
  is_owner: boolean;   // computed by backend from verified JWT, never exposes user_id
  created_at: string;
  updated_at: string;
}

async function authHeaders(): Promise<Record<string, string>> {
  const supabase = createClient();
  const { data: { session } } = await supabase.auth.getSession();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (session?.access_token) headers["Authorization"] = `Bearer ${session.access_token}`;
  return headers;
}

export async function getWisdomPosts(page = 1, perPage = 10): Promise<{ posts: WisdomPost[]; page: number }> {
  try {
    // Pass auth token so backend can compute is_owner on each post
    const supabase = createClient();
    const { data: { session } } = await supabase.auth.getSession();
    const headers: Record<string, string> = {};
    if (session?.access_token) headers["Authorization"] = `Bearer ${session.access_token}`;
    const res = await fetch(`${API_BASE}/api/wisdom?page=${page}&per_page=${perPage}`, { headers });
    if (!res.ok) return { posts: [], page };
    return res.json();
  } catch { return { posts: [], page }; }
}

export async function getPostsByUser(displayName: string, page = 1): Promise<WisdomPost[]> {
  try {
    const res = await fetch(`${API_BASE}/api/wisdom?page=${page}&user_display_name=${encodeURIComponent(displayName)}`);
    if (!res.ok) return [];
    const data = await res.json();
    return data.posts ?? [];
  } catch { return []; }
}

export async function createPost(content: string, contactEmail?: string, contactPhone?: string) {
  try {
    const headers = await authHeaders();
    const res = await fetch(`${API_BASE}/api/wisdom`, {
      method: "POST",
      headers,
      body: JSON.stringify({ content, contact_email: contactEmail || null, contact_phone: contactPhone || null }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const detail = data.detail || {};
      if (res.status === 429) {
        const used  = detail.used  ?? null;
        const limit = detail.limit ?? null;
        let err: string;
        if (detail.error === "daily_post_limit") {
          err = limit
            ? `You've posted ${used} of ${limit} times today. Come back tomorrow.`
            : "You've reached the daily post limit. Come back tomorrow.";
        } else {
          err = limit
            ? `You've used ${used} of ${limit} submission attempts today. Come back tomorrow.`
            : "Submission limit reached for today. Come back tomorrow.";
        }
        return { status: "error", message: err, error_type: detail.error };
      }
      return { status: "error", message: detail.message || "Failed to submit. Please try again." };
    }
    return data;
  } catch { return { status: "error", message: "Network error. Please try again." }; }
}

export async function editPost(postId: string, content: string, contactEmail?: string, contactPhone?: string) {
  try {
    const headers = await authHeaders();
    const res = await fetch(`${API_BASE}/api/wisdom/${postId}`, {
      method: "PATCH",
      headers,
      body: JSON.stringify({ content, contact_email: contactEmail || null, contact_phone: contactPhone || null }),
    });
    return res.json();
  } catch { return { status: "error", message: "Network error." }; }
}

export async function deletePost(postId: string): Promise<boolean> {
  try {
    const headers = await authHeaders();
    const res = await fetch(`${API_BASE}/api/wisdom/${postId}`, { method: "DELETE", headers });
    return res.ok;
  } catch { return false; }
}

export async function votePost(postId: string, vote: "up" | "down"): Promise<{ ok: boolean; action?: string }> {
  try {
    const headers = await authHeaders();
    const res = await fetch(`${API_BASE}/api/wisdom/${postId}/vote`, {
      method: "POST",
      headers,
      body: JSON.stringify({ vote }),
    });
    if (!res.ok) return { ok: false };
    return res.json();
  } catch { return { ok: false }; }
}

export async function getDisplayName(): Promise<string | null> {
  try {
    const headers = await authHeaders();
    const res = await fetch(`${API_BASE}/api/wisdom/me/display-name`, { headers });
    if (!res.ok) return null;
    const data = await res.json();
    return data.display_name ?? null;
  } catch { return null; }
}

export async function setDisplayName(name: string): Promise<{ ok: boolean; error?: string }> {
  try {
    const headers = await authHeaders();
    const res = await fetch(`${API_BASE}/api/wisdom/me/display-name`, {
      method: "PUT",
      headers,
      body: JSON.stringify({ display_name: name }),
    });
    if (res.ok) return { ok: true };
    const data = await res.json().catch(() => ({}));
    if (res.status === 409) {
      return { ok: false, error: data.detail?.message ?? `"${name}" is already taken. Please choose another name.` };
    }
    return { ok: false, error: data.detail?.message ?? "Could not save display name." };
  } catch { return { ok: false, error: "Network error. Please try again." }; }
}
