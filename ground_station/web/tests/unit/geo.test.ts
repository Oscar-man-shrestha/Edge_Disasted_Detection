import { describe, expect, it } from "vitest";
import { distanceM, interpolateAt, lerpAngle, pathDistanceM } from "../../src/lib/geo";

describe("geo", () => {
  it("distanceM matches the backend formula", () => {
    expect(distanceM({ lat: 12.97, lon: 77.59 }, { lat: 12.971, lon: 77.59 })).toBeCloseTo(111.32, 1);
  });
  it("pathDistanceM sums segments", () => {
    const p = [{ lat: 12.97, lon: 77.59 }, { lat: 12.971, lon: 77.59 }, { lat: 12.972, lon: 77.59 }];
    expect(pathDistanceM(p)).toBeCloseTo(222.64, 1);
    expect(pathDistanceM([])).toBe(0);
  });
  it("lerpAngle takes the short way round", () => {
    expect(lerpAngle(350, 10, 0.5)).toBeCloseTo(0, 6);
    expect(lerpAngle(10, 350, 0.25)).toBeCloseTo(5, 6);
    expect(lerpAngle(90, 180, 0.5)).toBeCloseTo(135, 6);
  });
  it("interpolateAt", () => {
    const s = [
      { t: 0, lat: 0, lon: 0, course_deg: 350 },
      { t: 10, lat: null, lon: null, course_deg: null },
      { t: 20, lat: 2, lon: 4, course_deg: 10 },
    ];
    const mid = interpolateAt(s, 10)!;
    expect(mid.lat).toBeCloseTo(1, 6);
    expect(mid.lon).toBeCloseTo(2, 6);
    expect(mid.course).toBeCloseTo(0, 6);
    expect(interpolateAt(s, -5)).toEqual({ lat: 0, lon: 0, course: 350 });
    expect(interpolateAt(s, 99)).toEqual({ lat: 2, lon: 4, course: 10 });
    expect(interpolateAt([], 1)).toBeNull();
    expect(interpolateAt([{ t: 0, lat: null, lon: null }], 1)).toBeNull();
  });
});
