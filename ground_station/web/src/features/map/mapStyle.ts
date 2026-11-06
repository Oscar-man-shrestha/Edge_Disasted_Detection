import type { LayerSpecification, StyleSpecification } from "@maplibre/maplibre-gl-style-spec";

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
      // dark: muted "tactical" basemap so the drone, track and alerts stand out
      { id: "osm", type: "raster", source: "osm", paint: dark
        ? { "raster-brightness-max": 0.62, "raster-saturation": -0.55, "raster-contrast": 0.1, "raster-fade-duration": 150 }
        : { "raster-brightness-max": 1, "raster-fade-duration": 150 } },
    ],
  };
}

export const ALERT_SOURCE_LAYER = "alerts-source";

/** Invisible layer on the clustered "alerts" source: MapLibre only loads tiles (and so
 *  answers querySourceFeatures) for sources that some layer uses. Markers are HTML. */
export function alertSourceLayer(): LayerSpecification {
  return { id: ALERT_SOURCE_LAYER, type: "circle", source: "alerts",
    paint: { "circle-opacity": 0, "circle-radius": 0, "circle-stroke-width": 0 } };
}
