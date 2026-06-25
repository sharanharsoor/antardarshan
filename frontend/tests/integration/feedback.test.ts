/**
 * Tests for feedback restore (getConversationFeedback) and the /api/feedback call.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";

const mockGetSession = vi.fn();
const mockFrom = vi.fn();
vi.mock("@/utils/supabase/client", () => ({
  createClient: () => ({ auth: { getSession: mockGetSession }, from: mockFrom }),
}));

import { getConversationFeedback } from "@/lib/conversations";

const SESSION = { data: { session: { user: { id: "user-1" }, access_token: "tok" } } };

beforeEach(() => {
  mockGetSession.mockResolvedValue(SESSION);
});

describe("getConversationFeedback", () => {
  it("returns empty map when not logged in", async () => {
    mockGetSession.mockResolvedValue({ data: { session: null } });
    expect(await getConversationFeedback("conv-1")).toEqual({});
  });

  it("returns empty map on DB error", async () => {
    mockFrom.mockReturnValue({
      select: vi.fn().mockReturnThis(),
      eq: vi.fn().mockReturnThis(),
      order: vi.fn().mockResolvedValue({ data: null }),
    });
    expect(await getConversationFeedback("conv-1")).toEqual({});
  });

  it("builds message_id → rating map from rows", async () => {
    const rows = [
      { message_id: "msg-1", rating: 1 },
      { message_id: "msg-2", rating: -1 },
    ];
    mockFrom.mockReturnValue({
      select: vi.fn().mockReturnThis(),
      eq: vi.fn().mockReturnThis(),
      order: vi.fn().mockResolvedValue({ data: rows }),
    });
    const result = await getConversationFeedback("conv-1");
    expect(result).toEqual({ "msg-1": 1, "msg-2": -1 });
  });

  it("last rating wins when duplicates exist (newest-first ordering)", async () => {
    // If upsert races and two rows exist, the first row (most recent) wins
    const rows = [
      { message_id: "msg-1", rating: -1 }, // most recent (bad rating)
      { message_id: "msg-1", rating: 1 },  // older (good rating, overridden)
    ];
    mockFrom.mockReturnValue({
      select: vi.fn().mockReturnThis(),
      eq: vi.fn().mockReturnThis(),
      order: vi.fn().mockResolvedValue({ data: rows }),
    });
    const result = await getConversationFeedback("conv-1");
    expect(result["msg-1"]).toBe(-1); // newest (first in array) wins
  });

  it("skips rows with null message_id", async () => {
    const rows = [
      { message_id: null, rating: 1 },
      { message_id: "msg-2", rating: -1 },
    ];
    mockFrom.mockReturnValue({
      select: vi.fn().mockReturnThis(),
      eq: vi.fn().mockReturnThis(),
      order: vi.fn().mockResolvedValue({ data: rows }),
    });
    const result = await getConversationFeedback("conv-1");
    expect(result).not.toHaveProperty("null");
    expect(result["msg-2"]).toBe(-1);
  });
});
