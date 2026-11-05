import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, exportUrl, snapUrl, updateAlert } from "../../src/lib/api";
import { alert } from "../fixtures/data";

describe("api", () => {
  afterEach(() => vi.unstubAllGlobals());
  it("updateAlert POSTs JSON and returns the alert", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: true, alert: alert(7) }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const a = await updateAlert(7, { status: "acknowledged" });
    expect(a.id).toBe(7);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/alerts/7");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({ status: "acknowledged" });
  });
  it("non-2xx throws ApiError with the status", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: "bad" }), { status: 400 })));
    await expect(updateAlert(7, { status: "new" })).rejects.toMatchObject({ status: 400 });
    await expect(updateAlert(7, { status: "new" })).rejects.toBeInstanceOf(ApiError);
  });
  it("urls", () => {
    expect(snapUrl("a b.jpg")).toBe("/snap/a%20b.jpg");
    expect(exportUrl(3, "kml")).toBe("/api/missions/3/export.kml");
  });
});
