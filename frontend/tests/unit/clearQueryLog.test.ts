import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// Mock Supabase client
const mockGetSession = vi.fn();
vi.mock("@/utils/supabase/client", () => ({
  createClient: () => ({ auth: { getSession: mockGetSession } }),
}));

import { clearQueryLog } from "@/lib/conversations";

describe("clearQueryLog", () => {
  beforeEach(() => {
    mockGetSession.mockResolvedValue({
      data: { session: { access_token: "tok-abc" } },
    });
  });

  afterEach(() => vi.unstubAllGlobals());

  it("returns false when no session", async () => {
    mockGetSession.mockResolvedValue({ data: { session: null } });
    expect(await clearQueryLog()).toBe(false);
  });

  it("calls DELETE /api/query-log with Authorization header", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true }));
    await clearQueryLog();
    expect(vi.mocked(fetch)).toHaveBeenCalledWith(
      expect.stringContaining("/api/query-log"),
      expect.objectContaining({
        method: "DELETE",
        headers: expect.objectContaining({ Authorization: "Bearer tok-abc" }),
      })
    );
  });

  it("returns true on 200 response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true }));
    expect(await clearQueryLog()).toBe(true);
  });

  it("returns false on non-ok response (503)", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 503 }));
    expect(await clearQueryLog()).toBe(false);
  });

  it("returns false on network error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network")));
    expect(await clearQueryLog()).toBe(false);
  });
});
