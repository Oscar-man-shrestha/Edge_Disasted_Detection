import "maplibre-gl/dist/maplibre-gl.css";
import "./map.css";
import { AttributionControl, LngLatBounds, Map as MLMap, Marker, type GeoJSONSource } from "maplibre-gl";
import { MapPinOff } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { DronePose } from "../../lib/geo";
import type { Alert, AlertType } from "../../lib/types";
import { isDark } from "../../hooks/useTheme";
import { useMapCommand, usePrefs } from "../../store/ui";
import { MapControls, type LayerToggles } from "./MapControls";
import { ATTRIBUTION, buildStyle } from "./mapStyle";
import { alertElement, clusterElement, droneElement } from "./markers";
import { useAnimatedDrone } from "./useAnimatedDrone";
import { hasWebGL } from "./webgl";

export interface MissionMapProps {
  mode: "live" | "replay";
  drone: DronePose | null;
  droneStale?: boolean;
  trail: [number, number][];          // [lon, lat]
  alerts: Alert[];
  selectedId?: number | null;
  onSelectAlert(id: number): void;
}

const CLUSTER_ABOVE = 25;
const DEFAULT_CENTER: [number, number] = [77.5905, 12.9715];

export function MissionMap(props: MissionMapProps) {
  const webgl = useMemo(hasWebGL, []);
  if (!webgl) {
    return (
      <div className="grid h-full w-full place-items-center bg-surface-2 p-6 text-center">
        <div className="max-w-sm">
          <MapPinOff className="mx-auto mb-2 text-muted" aria-hidden />
          <p className="font-semibold">Map needs WebGL</p>
          <p className="mt-1 text-sm text-text-2">This browser or device cannot run the 3D map. Camera, flight data, alerts, replay and analytics keep working.</p>
        </div>
      </div>
    );
  }
  return <MapInner {...props} />;
}

const located = (a: Alert) => a.lat != null && a.lon != null && Number.isFinite(a.lat) && Number.isFinite(a.lon);

function MapInner({ mode, drone, droneStale, trail, alerts, selectedId, onSelectAlert }: MissionMapProps) {
  const box = useRef<HTMLDivElement>(null);
  const [map, setMap] = useState<MLMap | null>(null);
  const prefs = usePrefs((s) => s.prefs);
  const setPrefs = usePrefs((s) => s.set);
  const [layers, setLayers] = useState<LayerToggles>({ trail: true, alerts: true, terrain: true, dim: false });
  const [hint, setHint] = useState<string | null>(null);
  const animated = useAnimatedDrone(mode === "live" ? drone : null);
  const pose = mode === "live" ? animated : drone;
  const fitted = useRef(false);
  const onSelect = useRef(onSelectAlert);
  onSelect.current = onSelectAlert;

  // ---- create the map once
  useEffect(() => {
    const m = new MLMap({
      container: box.current!, style: buildStyle({ dark: isDark() }), center: DEFAULT_CENTER, zoom: 16,
      attributionControl: false, maxPitch: 70, fadeDuration: 150,
    });
    m.addControl(new AttributionControl({ customAttribution: ATTRIBUTION, compact: true }), "bottom-right");
    m.on("load", () => {
      m.addSource("trail", { type: "geojson", lineMetrics: true, data: { type: "FeatureCollection", features: [] } });
      m.addLayer({
        id: "trail", type: "line", source: "trail", layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-width": 3,
          "line-gradient": ["interpolate", ["linear"], ["line-progress"], 0, "rgba(57,135,229,0.05)", 1, "rgba(57,135,229,0.95)"],
        },
      });
      setMap(m);
    });
    m.on("dragstart", (e: any) => { if (e.originalEvent) usePrefs.getState().set({ follow: false }); });
    if (window.location.search.includes("debug=1")) (window as any).__gsMap = m;
    return () => { m.remove(); setMap(null); };
  }, []);

  // ---- theme follows the document
  useEffect(() => {
    if (!map) return;
    const apply = () => {
      const dark = isDark();
      map.setPaintProperty("background", "background-color", dark ? "#10141b" : "#e9edf2");
      map.setPaintProperty("osm", "raster-brightness-max", layers.dim ? 0.5 : dark ? 0.75 : 1);
    };
    apply();
    const obs = new MutationObserver(apply);
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    const mq = window.matchMedia?.("(prefers-color-scheme: dark)");
    mq?.addEventListener?.("change", apply);
    return () => { obs.disconnect(); mq?.removeEventListener?.("change", apply); };
  }, [map, layers.dim]);

  // ---- trail
  useEffect(() => {
    if (!map) return;
    const src = map.getSource("trail") as GeoJSONSource | undefined;
    const coords = layers.trail ? trail : [];
    src?.setData({ type: "FeatureCollection", features: coords.length >= 2
      ? [{ type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: coords } }] : [] });
  }, [map, trail, layers.trail]);

  // ---- drone marker
  const droneMarker = useRef<Marker | null>(null);
  useEffect(() => {
    if (!map) return;
    if (!pose) { droneMarker.current?.remove(); droneMarker.current = null; return; }
    if (!droneMarker.current) {
      droneMarker.current = new Marker({ element: droneElement(), rotationAlignment: "map", pitchAlignment: "map" })
        .setLngLat([pose.lon, pose.lat]).addTo(map);
    }
    droneMarker.current.setLngLat([pose.lon, pose.lat]).setRotation(pose.course ?? 0);
    droneMarker.current.getElement().classList.toggle("gs-stale", !!droneStale);
    if (mode === "live" && prefs.follow && !droneStale) {
      map.setCenter([pose.lon, pose.lat]);
      if (prefs.headingUp && pose.course != null) map.setBearing(pose.course);
    }
  }, [map, pose, droneStale, mode, prefs.follow, prefs.headingUp]);
  useEffect(() => () => { droneMarker.current?.remove(); droneMarker.current = null; }, [map]);

  // ---- alert markers (HTML), clustered above CLUSTER_ABOVE
  const alertMarkers = useRef(new Map<string, Marker>());
  const shown = useMemo(() => (layers.alerts ? alerts.filter(located) : []), [alerts, layers.alerts]);
  const renderAlerts = useCallback(() => {
    if (!map) return;
    const keep = new Set<string>();
    const put = (key: string, lngLat: [number, number], make: () => HTMLElement) => {
      keep.add(key);
      const old = alertMarkers.current.get(key);
      if (old) { old.remove(); }
      alertMarkers.current.set(key, new Marker({ element: make() }).setLngLat(lngLat).addTo(map));
    };
    if (shown.length <= CLUSTER_ABOVE) {
      for (const a of shown) put(`a${a.id}`, [a.lon!, a.lat!], () => alertElement(a, a.id === selectedId, onSelect.current));
    } else {
      const byId = new Map(shown.map((a) => [a.id, a]));
      for (const f of map.querySourceFeatures("alerts")) {
        const p = f.properties as any;
        const [lon, lat] = (f.geometry as any).coordinates as [number, number];
        if (p.cluster) {
          const key = `c${p.cluster_id}`;
          if (keep.has(key)) continue;
          const counts = { person: p.person ?? 0, fire: p.fire ?? 0, smoke: p.smoke ?? 0 } as Record<AlertType, number>;
          put(key, [lon, lat], () => clusterElement(counts, p.point_count, () => map.easeTo({ center: [lon, lat], zoom: map.getZoom() + 2 })));
        } else {
          const a = byId.get(p.id);
          if (a && !keep.has(`a${a.id}`)) put(`a${a.id}`, [lon, lat], () => alertElement(a, a.id === selectedId, onSelect.current));
        }
      }
    }
    for (const [k, mk] of alertMarkers.current) if (!keep.has(k)) { mk.remove(); alertMarkers.current.delete(k); }
  }, [map, shown, selectedId]);

  useEffect(() => {
    if (!map) return;
    const clustered = shown.length > CLUSTER_ABOVE;
    if (clustered) {
      const data = { type: "FeatureCollection" as const, features: shown.map((a) => ({
        type: "Feature" as const, properties: { id: a.id, type: a.type },
        geometry: { type: "Point" as const, coordinates: [a.lon!, a.lat!] } })) };
      const src = map.getSource("alerts") as GeoJSONSource | undefined;
      if (src) src.setData(data);
      else map.addSource("alerts", {
        type: "geojson", data, cluster: true, clusterMaxZoom: 17, clusterRadius: 40,
        clusterProperties: {
          person: ["+", ["case", ["==", ["get", "type"], "person"], 1, 0]],
          fire: ["+", ["case", ["==", ["get", "type"], "fire"], 1, 0]],
          smoke: ["+", ["case", ["==", ["get", "type"], "smoke"], 1, 0]],
        },
      });
      let pending = false;
      const onRender = () => {
        if (pending) return;
        pending = true;
        requestAnimationFrame(() => { pending = false; renderAlerts(); });
      };
      map.on("moveend", onRender);
      map.on("sourcedata", onRender);
      onRender();
      return () => { map.off("moveend", onRender); map.off("sourcedata", onRender); };
    }
    if (map.getSource("alerts")) map.removeSource("alerts");
    renderAlerts();
    return undefined;
  }, [map, shown, renderAlerts]);
  useEffect(() => () => { alertMarkers.current.forEach((m) => m.remove()); alertMarkers.current.clear(); }, [map]);

  // ---- 3D + terrain
  useEffect(() => {
    if (!map) return;
    if (!prefs.map3d) { map.setTerrain(null); map.easeTo({ pitch: 0, duration: 600 }); setHint(null); return; }
    map.easeTo({ pitch: 60, duration: 800 });
    if (!layers.terrain) { map.setTerrain(null); return; }
    let errors = 0;
    const onErr = (e: any) => { if (e?.sourceId === "terrain" || e?.source?.id === "terrain") errors++; };
    map.on("error", onErr);
    map.setTerrain({ source: "terrain", exaggeration: 1.3 });
    const t = setTimeout(() => {
      if (errors > 0) { map.setTerrain(null); setHint("Terrain not cached for this area"); }
    }, 3000);
    return () => { clearTimeout(t); map.off("error", onErr); };
  }, [map, prefs.map3d, layers.terrain]);

  // ---- fit / commands
  const fitAll = useCallback(() => {
    if (!map) return;
    const b = new LngLatBounds();
    trail.forEach((c) => b.extend(c));
    alerts.filter(located).forEach((a) => b.extend([a.lon!, a.lat!]));
    if (pose) b.extend([pose.lon, pose.lat]);
    if (!b.isEmpty()) map.fitBounds(b, { padding: 60, maxZoom: 18, duration: 600 });
  }, [map, trail, alerts, pose]);

  useEffect(() => {
    if (!map || fitted.current) return;
    if (trail.length || alerts.some(located) || pose) {
      fitted.current = true;
      if (mode === "live" && pose && prefs.follow) map.jumpTo({ center: [pose.lon, pose.lat], zoom: 17 });
      else fitAll();
    }
  }, [map, trail.length, alerts, pose, mode, prefs.follow, fitAll]);

  const cmd = useMapCommand((s) => s.cmd);
  useEffect(() => {
    if (!map || !cmd) return;
    if (cmd.type === "fit") fitAll();
    else if (cmd.type === "north") map.easeTo({ bearing: 0, duration: 500 });
    else if (cmd.type === "flyTo") {
      if (mode === "live") setPrefs({ follow: false });
      map.flyTo({ center: [cmd.lon, cmd.lat], zoom: Math.max(map.getZoom(), 17), duration: 900 });
    }
  }, [cmd]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="relative h-full w-full" style={{ background: "var(--gs-map-grid)" }}>
      <div ref={box} className="absolute inset-0" aria-label="Mission map" role="region" />
      {map && <MapControls map={map} layers={layers} onLayers={setLayers} onFit={fitAll} live={mode === "live"} />}
      {hint && (
        <div role="status" className="absolute left-1/2 top-3 z-10 -translate-x-1/2 rounded-full border border-line bg-surface/95 px-3 py-1 text-xs text-text-2 shadow-panel">
          {hint} — <button type="button" className="underline" onClick={() => setHint(null)}>dismiss</button>
        </div>
      )}
    </div>
  );
}
