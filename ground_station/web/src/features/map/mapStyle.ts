import type { StyleSpecification } from "@maplibre/maplibre-gl-style-spec";

export const ATTRIBUTION = "© OpenStreetMap contributors · Terrain: Mapzen, AWS Terrain Tiles";

/** Fully offline style: only the station's /tiles and /terrain proxies; no glyph/sprite servers. */
export function buildStyle({ dark }: { dark: boolean }): StyleSpecification {
  return {
    version: 8,
    sources: {
      osm: { type: "raster", tiles: ["/tiles/{z}/{x}/{y}.png"], tileSize: 256, maxzoom: 19 },
      terrain: { type: "raster-dem", tiles: ["/terrain/{z}/{x}/{y}.png"], encoding: "terrarium", maxzoom: 15, tileSize: 256 },
    },
    layers: [
      { id: "background", type: "background", paint: { "background-color": dark ? "#10141b" : "#e9edf2" } },
      { id: "osm", type: "raster", source: "osm", paint: { "raster-brightness-max": dark ? 0.75 : 1, "raster-fade-duration": 150 } },
    ],
  };
}
