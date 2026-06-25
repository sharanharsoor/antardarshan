/**
 * Unit tests for wisdom.ts API client helpers.
 * All network calls are mocked — no real backend or Supabase required.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

const mockGetSession = vi.fn();
vi.mock("@/utils/supabase/client", () => ({
  createClient: () => ({ auth: { getSession: mockGetSession } }),
}));

import {
  getWisdomPosts, createPost, deletePost, votePost,
  getDisplayName, setDisplayName,
} from "@/lib/wisdom";

const SESSION = { data: { session: { access_token: "tok" } } };

beforeEach(() => {
  mockGetSession.mockResolvedValue(SESSION);
});

afterEach(() => vi.unstubAllGlobals());

// ── getWisdomPosts ────────────────────────────────────────────────────

describe("getWisdomPosts", () => {
  it("fetches public feed with optional auth header", async () => {
    const posts = [{ id: "p1", content: "Truth" }];
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ posts, page: 1 }),
    }));
    const result = await getWisdomPosts(1, 10);
    expect(result.posts).toEqual(posts);
    // URL must be correct; options (headers) are passed but vary by auth state
    expect(vi.mocked(fetch)).toHaveBeenCalledWith(
      expect.stringContaining("/api/wisdom?page=1&per_page=10"),
      expect.anything()
    );
  });

  it("returns empty posts on network failure", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network")));
    const result = await getWisdomPosts();
    expect(result.posts).toEqual([]);
  });
});

// ── createPost ────────────────────────────────────────────────────────

describe("createPost", () => {
  it("sends POST with auth header and content", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: "approved", post: { id: "p1" } }),
    }));
    const result = await createPost("Karma is real.");
    expect(result.status).toBe("approved");
    expect(vi.mocked(fetch)).toHaveBeenCalledWith(
      expect.stringContaining("/api/wisdom"),
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ Authorization: "Bearer tok" }),
      })
    );
  });

  it("handles 429 daily_post_limit with descriptive message", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false,
      status: 429,
      json: async () => ({ detail: { error: "daily_post_limit", used: 2, limit: 2 } }),
    }));
    const result = await createPost("Extra post");
    expect(result.status).toBe("error");
    expect(result.error_type).toBe("daily_post_limit");
    expect(result.message).toContain("2");
  });

  it("handles 429 moderation_limit with attempt count", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false,
      status: 429,
      json: async () => ({ detail: { error: "moderation_limit", used: 5, limit: 5 } }),
    }));
    const result = await createPost("Post");
    expect(result.status).toBe("error");
    expect(result.error_type).toBe("moderation_limit");
    expect(result.message).toContain("5 of 5");
  });

  it("returns rejected status when content fails moderation", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: "rejected", message: "Political content" }),
    }));
    const result = await createPost("Vote for me!");
    expect(result.status).toBe("rejected");
  });

  it("returns error on network failure", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network")));
    const result = await createPost("Hello");
    expect(result.status).toBe("error");
    expect(result.message).toContain("Network error");
  });
});

// ── deletePost ────────────────────────────────────────────────────────

describe("deletePost", () => {
  it("sends DELETE with auth header", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true }));
    const ok = await deletePost("post-123");
    expect(ok).toBe(true);
    expect(vi.mocked(fetch)).toHaveBeenCalledWith(
      expect.stringContaining("/api/wisdom/post-123"),
      expect.objectContaining({ method: "DELETE" })
    );
  });

  it("returns false on non-ok response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 404 }));
    expect(await deletePost("bad-id")).toBe(false);
  });

  it("returns false on network error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network")));
    expect(await deletePost("id")).toBe(false);
  });
});

// ── votePost ──────────────────────────────────────────────────────────

describe("votePost", () => {
  it("sends POST to vote endpoint with vote direction", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ ok: true, action: "added" }),
    }));
    const result = await votePost("p1", "up");
    expect(result.ok).toBe(true);
    expect(vi.mocked(fetch)).toHaveBeenCalledWith(
      expect.stringContaining("/api/wisdom/p1/vote"),
      expect.objectContaining({ method: "POST" })
    );
  });

  it("returns ok:false when not authenticated (401)", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 401 }));
    const result = await votePost("p1", "down");
    expect(result.ok).toBe(false);
  });
});

// ── display name ──────────────────────────────────────────────────────

describe("getDisplayName", () => {
  it("returns display name from API", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ display_name: "WiseSage" }),
    }));
    const name = await getDisplayName();
    expect(name).toBe("WiseSage");
  });

  it("returns null when not set", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ display_name: null }),
    }));
    expect(await getDisplayName()).toBeNull();
  });

  it("returns null on failure", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network")));
    expect(await getDisplayName()).toBeNull();
  });
});

describe("setDisplayName", () => {
  it("returns ok:true on success", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true }));
    expect(await setDisplayName("Sage")).toEqual({ ok: true });
  });

  it("returns ok:false on failure", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false, status: 400,
      json: async () => ({ detail: { message: "Too long" } }),
    }));
    const result = await setDisplayName("");
    expect(result.ok).toBe(false);
  });

  it("returns ok:false with 'taken' message on 409", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false, status: 409,
      json: async () => ({ detail: { error: "name_taken", message: "'Sage' is already taken. Please choose a different display name." } }),
    }));
    const result = await setDisplayName("Sage");
    expect(result.ok).toBe(false);
    expect(result.error).toContain("taken");
  });
});
