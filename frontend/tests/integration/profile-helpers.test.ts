/**
 * Integration tests for profile-specific Supabase helpers.
 * Supabase client is fully mocked.
 */
import { describe, it, expect, vi } from "vitest";

const mockFrom = vi.fn();
const mockGetUser = vi.fn();
const mockSupabase = {
  from: mockFrom,
  auth: { getUser: mockGetUser },
};
vi.mock("@/utils/supabase/client", () => ({
  createClient: () => mockSupabase,
}));

import {
  getAllProgress, getAllBookmarks, getAllHighlights, getQueriesThisMonth,
} from "@/lib/supabase-reader";

const mockUser = { id: "user-abc" };

const orderChain = (data: unknown) => ({
  select: vi.fn().mockReturnThis(),
  eq: vi.fn().mockReturnThis(),
  gte: vi.fn().mockReturnThis(),
  order: vi.fn().mockResolvedValue({ data }),
});

describe("getAllProgress", () => {
  it("returns empty array when not logged in", async () => {
    mockGetUser.mockResolvedValue({ data: { user: null } });
    expect(await getAllProgress()).toEqual([]);
  });

  it("returns all progress rows for logged-in user", async () => {
    mockGetUser.mockResolvedValue({ data: { user: mockUser } });
    const rows = [
      { slug: "gita", chapter: 5, verse: 1, updated_at: "2026-01-01" },
      { slug: "dhammapada", chapter: 2, verse: 3, updated_at: "2026-01-02" },
    ];
    mockFrom.mockReturnValue(orderChain(rows));

    const result = await getAllProgress();
    expect(result).toHaveLength(2);
    expect(result[0].slug).toBe("gita");
    expect(result[1].slug).toBe("dhammapada");
  });

  it("queries the reading_progress table", async () => {
    mockGetUser.mockResolvedValue({ data: { user: mockUser } });
    mockFrom.mockReturnValue(orderChain([]));

    await getAllProgress();
    expect(mockFrom).toHaveBeenCalledWith("reading_progress");
  });

  it("returns empty array on network error", async () => {
    mockGetUser.mockRejectedValue(new Error("network"));
    expect(await getAllProgress()).toEqual([]);
  });
});

describe("getAllBookmarks", () => {
  it("returns empty array when not logged in", async () => {
    mockGetUser.mockResolvedValue({ data: { user: null } });
    expect(await getAllBookmarks()).toEqual([]);
  });

  it("returns all bookmarks across all scriptures", async () => {
    mockGetUser.mockResolvedValue({ data: { user: mockUser } });
    const bms = [
      { id: "b1", slug: "gita", scripture: "Bhagavad Gita", chapter: 2, verse: 47 },
      { id: "b2", slug: "dhammapada", scripture: "Dhammapada", chapter: 1, verse: 5 },
      { id: "b3", slug: "gita", scripture: "Bhagavad Gita", chapter: 3, verse: 19 },
    ];
    mockFrom.mockReturnValue(orderChain(bms));

    const result = await getAllBookmarks();
    expect(result).toHaveLength(3);
  });

  it("queries the bookmarks table", async () => {
    mockGetUser.mockResolvedValue({ data: { user: mockUser } });
    mockFrom.mockReturnValue(orderChain([]));

    await getAllBookmarks();
    expect(mockFrom).toHaveBeenCalledWith("bookmarks");
  });
});

describe("getAllHighlights", () => {
  it("returns empty array when not logged in", async () => {
    mockGetUser.mockResolvedValue({ data: { user: null } });
    expect(await getAllHighlights()).toEqual([]);
  });

  it("returns highlights across all chapters and scriptures", async () => {
    mockGetUser.mockResolvedValue({ data: { user: mockUser } });
    const hls = [
      { id: "h1", slug: "gita", chapter: 2, verse: 47, selected_text: "karma", color: "yellow" },
      { id: "h2", slug: "gita", chapter: 3, verse: 5,  selected_text: "duty",  color: "green" },
    ];
    mockFrom.mockReturnValue(orderChain(hls));

    const result = await getAllHighlights();
    expect(result).toHaveLength(2);
  });

  it("queries the highlights table", async () => {
    mockGetUser.mockResolvedValue({ data: { user: mockUser } });
    mockFrom.mockReturnValue(orderChain([]));

    await getAllHighlights();
    expect(mockFrom).toHaveBeenCalledWith("highlights");
  });
});

describe("getQueriesThisMonth", () => {
  it("returns 0 when not logged in", async () => {
    mockGetUser.mockResolvedValue({ data: { user: null } });
    expect(await getQueriesThisMonth()).toBe(0);
  });

  it("returns count from user_query_log", async () => {
    mockGetUser.mockResolvedValue({ data: { user: mockUser } });
    const chain = {
      select: vi.fn().mockReturnThis(),
      eq: vi.fn().mockReturnThis(),
      gte: vi.fn().mockResolvedValue({ count: 42 }),
    };
    mockFrom.mockReturnValue(chain);

    expect(await getQueriesThisMonth()).toBe(42);
    expect(mockFrom).toHaveBeenCalledWith("user_query_log");
  });

  it("queries with a date filter for last 30 days", async () => {
    mockGetUser.mockResolvedValue({ data: { user: mockUser } });
    const chain = {
      select: vi.fn().mockReturnThis(),
      eq: vi.fn().mockReturnThis(),
      gte: vi.fn().mockResolvedValue({ count: 10 }),
    };
    mockFrom.mockReturnValue(chain);

    await getQueriesThisMonth();
    // gte should be called with queried_at and a date ~30 days ago
    expect(chain.gte).toHaveBeenCalledWith("queried_at", expect.stringMatching(/^\d{4}-\d{2}-\d{2}/));
  });

  it("returns 0 on network error", async () => {
    mockGetUser.mockRejectedValue(new Error("network"));
    expect(await getQueriesThisMonth()).toBe(0);
  });
});
