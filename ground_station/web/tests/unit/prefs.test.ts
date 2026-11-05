import { afterEach, describe, expect, it, vi } from "vitest";
import { DEFAULT_PREFS, loadPrefs, savePrefs } from "../../src/lib/prefs";

describe("prefs", () => {
  afterEach(() => vi.restoreAllMocks());
  it("defaults when storage throws", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("blocked"); });
    expect(loadPrefs()).toEqual(DEFAULT_PREFS);
  });
  it("round-trips", () => {
    savePrefs({ ...DEFAULT_PREFS, mute: true, types: ["fire"] });
    expect(loadPrefs()).toMatchObject({ mute: true, types: ["fire"], follow: true });
  });
  it("save never throws", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("full"); });
    expect(() => savePrefs(DEFAULT_PREFS)).not.toThrow();
  });
});
