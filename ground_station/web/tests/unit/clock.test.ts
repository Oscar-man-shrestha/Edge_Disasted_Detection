import { describe, expect, it } from "vitest";
import { createClock } from "../../src/lib/clock";

describe("clock", () => {
  it("tracks server time from a sync point", () => {
    const c = createClock(() => 5_000);
    c.sync(1000, 0);
    expect(c.now()).toBeCloseTo(1005, 6);
  });
  it("ignores a browser clock that is hours off", () => {
    let local = 1_700_000_000_000 - 3 * 3600_000; // browser 3 h behind
    const c = createClock(() => local);
    c.sync(1_700_000_000, local);
    local += 2_000;
    expect(c.now()).toBeCloseTo(1_700_000_002, 6);
  });
  it("returns local seconds before the first sync", () => {
    const c = createClock(() => 42_000);
    expect(c.now()).toBe(42);
  });
});
