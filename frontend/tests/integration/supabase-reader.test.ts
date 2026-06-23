/**
 * Integration tests for supabase-reader.ts helpers.
 * The Supabase client is fully mocked — no network calls, no real DB.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock the Supabase client module before any imports
const mockFrom = vi.fn();
const mockGetUser = vi.fn();
const mockGetSession = vi.fn();
const mockSupabase = {
  from: mockFrom,
  auth: { getUser: mockGetUser, getSession: mockGetSession },
};
vi.mock("@/utils/supabase/client", () => ({
  createClient: () => mockSupabase,
}));

import {
  getBookmarksForSlug, removeBookmark,
  getHighlightsForChapter, saveHighlight, deleteHighlight, updateHighlightNote,
  getCurrentUserId,
} from "@/lib/supabase-reader";

const mockUser = { id: "user-123" };
const mockSession = { user: mockUser };


describe("getCurrentUserId", () => {
  it("returns user id when session exists", async () => {
    mockGetSession.mockResolvedValue({ data: { session: mockSession } });
    const id = await getCurrentUserId();
    expect(id).toBe("user-123");
  });

  it("returns null when no session", async () => {
    mockGetSession.mockResolvedValue({ data: { session: null } });
    const id = await getCurrentUserId();
    expect(id).toBeNull();
  });

  it("returns null on network error", async () => {
    mockGetSession.mockRejectedValue(new Error("network error"));
    const id = await getCurrentUserId();
    expect(id).toBeNull();
  });
});

describe("getBookmarksForSlug", () => {
  it("returns empty array when not logged in", async () => {
    mockGetUser.mockResolvedValue({ data: { user: null } });
    const result = await getBookmarksForSlug("gita");
    expect(result).toEqual([]);
  });

  it("returns empty array on Supabase error", async () => {
    mockGetUser.mockRejectedValue(new Error("fetch failed"));
    const result = await getBookmarksForSlug("gita");
    expect(result).toEqual([]);
  });

  it("calls correct table and filters when logged in", async () => {
    mockGetUser.mockResolvedValue({ data: { user: mockUser } });
    const mockData = [{ id: "bm-1", slug: "gita", verse: 1, chapter: 1 }];
    const chain = {
      select: vi.fn().mockReturnThis(),
      eq: vi.fn().mockReturnThis(),
      order: vi.fn().mockResolvedValue({ data: mockData }),
    };
    mockFrom.mockReturnValue(chain);

    const result = await getBookmarksForSlug("gita");
    expect(mockFrom).toHaveBeenCalledWith("bookmarks");
    expect(result).toEqual(mockData);
  });
});

describe("removeBookmark", () => {
  it("returns true when delete succeeds", async () => {
    const chain = {
      delete: vi.fn().mockReturnThis(),
      eq: vi.fn().mockResolvedValue({ error: null }),
    };
    mockFrom.mockReturnValue(chain);
    expect(await removeBookmark("bm-id")).toBe(true);
  });

  it("returns false when delete fails", async () => {
    const chain = {
      delete: vi.fn().mockReturnThis(),
      eq: vi.fn().mockResolvedValue({ error: new Error("rls violation") }),
    };
    mockFrom.mockReturnValue(chain);
    expect(await removeBookmark("bm-id")).toBe(false);
  });
});

describe("getHighlightsForChapter", () => {
  it("returns empty array when no session", async () => {
    mockGetSession.mockResolvedValue({ data: { session: null } });
    expect(await getHighlightsForChapter("gita", 1)).toEqual([]);
  });

  it("returns highlights for the correct chapter", async () => {
    mockGetSession.mockResolvedValue({ data: { session: mockSession } });
    const highlights = [
      { id: "hl-1", slug: "gita", chapter: 1, verse: 2, selected_text: "karma", color: "yellow" },
    ];
    const chain = {
      select: vi.fn().mockReturnThis(),
      eq: vi.fn().mockReturnThis(),
      order: vi.fn().mockResolvedValue({ data: highlights }),
    };
    mockFrom.mockReturnValue(chain);

    const result = await getHighlightsForChapter("gita", 1);
    expect(result).toEqual(highlights);
  });
});

describe("saveHighlight", () => {
  beforeEach(() => {
    mockGetUser.mockResolvedValue({ data: { user: mockUser } });
  });

  it("returns null when not logged in", async () => {
    mockGetUser.mockResolvedValue({ data: { user: null } });
    const result = await saveHighlight("gita", 1, 1, "karma", 0, "yellow");
    expect(result).toBeNull();
  });

  it("inserts with correct fields and returns saved highlight", async () => {
    const saved = { id: "hl-new", slug: "gita", chapter: 1, verse: 1,
      selected_text: "karma", selected_occurrence: 0, color: "yellow", note: null };
    const chain = {
      insert: vi.fn().mockReturnThis(),
      select: vi.fn().mockReturnThis(),
      single: vi.fn().mockResolvedValue({ data: saved, error: null }),
    };
    mockFrom.mockReturnValue(chain);

    const result = await saveHighlight("gita", 1, 1, "karma", 0, "yellow");
    expect(mockFrom).toHaveBeenCalledWith("highlights");
    expect(chain.insert).toHaveBeenCalledWith(
      expect.objectContaining({ user_id: "user-123", slug: "gita", selected_text: "karma" })
    );
    expect(result).toEqual(saved);
  });

  it("returns null when DB insert fails", async () => {
    const chain = {
      insert: vi.fn().mockReturnThis(),
      select: vi.fn().mockReturnThis(),
      single: vi.fn().mockResolvedValue({ data: null, error: new Error("constraint") }),
    };
    mockFrom.mockReturnValue(chain);
    expect(await saveHighlight("gita", 1, 1, "karma", 0, "yellow")).toBeNull();
  });
});

describe("updateHighlightNote", () => {
  it("returns true on success", async () => {
    const chain = {
      update: vi.fn().mockReturnThis(),
      eq: vi.fn().mockResolvedValue({ error: null }),
    };
    mockFrom.mockReturnValue(chain);
    expect(await updateHighlightNote("hl-1", "my note")).toBe(true);
  });

  it("sets note to null when empty string passed", async () => {
    const chain = {
      update: vi.fn().mockReturnThis(),
      eq: vi.fn().mockResolvedValue({ error: null }),
    };
    mockFrom.mockReturnValue(chain);
    await updateHighlightNote("hl-1", "");
    expect(chain.update).toHaveBeenCalledWith(
      expect.objectContaining({ note: null })
    );
  });
});

describe("deleteHighlight", () => {
  it("returns true when delete succeeds", async () => {
    const chain = {
      delete: vi.fn().mockReturnThis(),
      eq: vi.fn().mockResolvedValue({ error: null }),
    };
    mockFrom.mockReturnValue(chain);
    expect(await deleteHighlight("hl-1")).toBe(true);
  });

  it("returns false on error", async () => {
    const chain = {
      delete: vi.fn().mockReturnThis(),
      eq: vi.fn().mockResolvedValue({ error: new Error("rls") }),
    };
    mockFrom.mockReturnValue(chain);
    expect(await deleteHighlight("hl-1")).toBe(false);
  });
});
