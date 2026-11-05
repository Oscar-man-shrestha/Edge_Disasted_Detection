import { describe, expect, it } from "vitest";
import { fmtClock, fmtCoord, fmtDuration, fmtNum } from "../../src/lib/format";

describe("format", () => {
  it("fmtNum", () => {
    expect(fmtNum(null)).toBe("—");
    expect(fmtNum(undefined)).toBe("—");
    expect(fmtNum(NaN)).toBe("—");
    expect(fmtNum("3")).toBe("—");
    expect(fmtNum(2.345, 1)).toBe("2.3");
    expect(fmtNum(7)).toBe("7");
  });
  it("fmtDuration", () => {
    expect(fmtDuration(3725)).toBe("01:02:05");
    expect(fmtDuration(-5)).toBe("00:00:00");
    expect(fmtDuration(null)).toBe("—");
  });
  it("fmtCoord", () => {
    expect(fmtCoord(null, 1)).toBe("no GPS fix");
    expect(fmtCoord(12.9715, 77.5905)).toBe("12.971500, 77.590500");
  });
  it("fmtClock", () => {
    expect(fmtClock(null)).toBe("—");
    expect(fmtClock(0)).toMatch(/^\d{2}:\d{2}:\d{2}$/);
  });
});
