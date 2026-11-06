import { describe, expect, it } from "vitest";
import { parseCoords, spreadOffsets } from "../../src/lib/geo";

describe("parseCoords", () => {
  it.each([
    ["12.97, 77.59", 12.97, 77.59], ["12.97 77.59", 12.97, 77.59], ["  12.97,77.59 ", 12.97, 77.59],
    ["12.97N 77.59E", 12.97, 77.59], ["12.97°S, 77.59°W", -12.97, -77.59], ["(-33.86, 151.21)", -33.86, 151.21],
    ["151.21, -33.86", -33.86, 151.21],                   // lon first by mistake: 151 cannot be a latitude
    ["77.59, 12.97", 77.59, 12.97],                       // both valid latitudes: kept as typed
    ["12 77", 12, 77],
  ])("%s", (txt, lat, lon) => expect(parseCoords(txt)).toEqual({ lat, lon }));

  it.each(["", "alert 5", "fire", "12.97", "95, 200", "12.97, 77.59, 3", "abc, def"])("rejects %j", (txt) =>
    expect(parseCoords(txt)).toBeNull());
});

describe("spreadOffsets", () => {
  it("leaves lone markers where they are", () => {
    const { offsets, hubs } = spreadOffsets([{ id: 1, lat: 12.97, lon: 77.59 }, { id: 2, lat: 12.98, lon: 77.59 }]);
    expect(offsets.size).toBe(0);
    expect(hubs).toEqual([]);
  });

  it("fans out markers at the same spot without overlapping, around one hub", () => {
    const same = [5, 1, 3, 2].map((id) => ({ id, lat: 12.973, lon: 77.5915 + id * 1e-7 }));   // < 1 m apart
    const { offsets, hubs } = spreadOffsets([...same, { id: 9, lat: 13, lon: 78 }]);
    expect(hubs).toHaveLength(1);
    expect(hubs[0].legs).toHaveLength(4);
    expect([...offsets.keys()].sort()).toEqual([1, 2, 3, 5]);
    expect(offsets.get(1)).toEqual([0, -24]);                                              // first at 12 o'clock
    const pts = [...offsets.values()];
    for (let i = 0; i < pts.length; i++) for (let j = i + 1; j < pts.length; j++)
      expect(Math.hypot(pts[i][0] - pts[j][0], pts[i][1] - pts[j][1])).toBeGreaterThanOrEqual(30);
  });

  it("bigger groups get a bigger ring so pins still do not touch", () => {
    const many = Array.from({ length: 12 }, (_, i) => ({ id: i + 1, lat: 1, lon: 1 }));
    const pts = [...spreadOffsets(many).offsets.values()];
    const d = Math.hypot(pts[0][0] - pts[1][0], pts[0][1] - pts[1][1]);
    expect(d).toBeGreaterThanOrEqual(30);
  });
});
