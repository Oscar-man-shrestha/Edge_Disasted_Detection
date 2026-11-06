import { describe, expect, it } from "vitest";
import { ATTRIBUTION, buildStyle } from "../../src/features/map/mapStyle";

describe("buildStyle", () => {
  it("uses only the station's tile and terrain proxies", () => {
    const s = buildStyle({ dark: true });
    const osm = s.sources.osm as any, terrain = s.sources.terrain as any;
    expect(osm).toMatchObject({ type: "raster", tiles: ["/tiles/{z}/{x}/{y}.png"], tileSize: 256, maxzoom: 19 });
    expect(terrain).toMatchObject({ type: "raster-dem", tiles: ["/terrain/{z}/{x}/{y}.png"], encoding: "terrarium", maxzoom: 15, tileSize: 256 });
    const json = JSON.stringify(s);
    expect(json).not.toMatch(/https?:/);
    expect(s).not.toHaveProperty("glyphs");
    expect(s).not.toHaveProperty("sprite");
    expect(s.layers.map((l) => l.id)).toEqual(["background", "osm"]);
  });
  it("dims and desaturates the basemap in dark mode only", () => {
    const dark = buildStyle({ dark: true }).layers[1] as any;
    const light = buildStyle({ dark: false }).layers[1] as any;
    expect(dark.paint["raster-brightness-max"]).toBeLessThan(0.75);
    expect(dark.paint["raster-saturation"]).toBeLessThan(0);
    expect(light.paint["raster-brightness-max"]).toBe(1);
    expect(light.paint["raster-saturation"]).toBeUndefined();
  });
  it("attribution text", () => {
    expect(ATTRIBUTION).toBe("© OpenStreetMap contributors · Terrain: Mapzen, AWS Terrain Tiles");
  });
});
