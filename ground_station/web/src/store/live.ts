import { create } from "zustand";
import { createClock, type Clock } from "../lib/clock";
import { isNum } from "../lib/format";
import type { Prefs } from "../lib/prefs";
import { PRIORITY, type Alert, type LinkInfo, type Mission, type Preview, type StateResponse,
  type Telemetry, type TrackPoint } from "../lib/types";
import type { ConnectionState } from "../lib/sse";

export const LINK_LOST_S = 3;

export interface LiveState {
  clock: Clock;
  mission: Mission | null;
  missions: Mission[];
  telemetry: Telemetry | null;
  telemetryAt: number | null;      // server time of the last telemetry
  preview: Preview | null;
  alerts: Record<number, Alert>;
  track: TrackPoint[];
  seen: Set<number>;
  loaded: boolean;
  connection: ConnectionState;
  hydrate(s: StateResponse): Alert[];
  applyEvent(name: string, data: any): { notify?: Alert };
  setConnection(c: ConnectionState): void;
  reset(): void;
}

const initial = () => ({
  clock: createClock(), mission: null, missions: [], telemetry: null, telemetryAt: null,
  preview: null, alerts: {}, track: [], seen: new Set<number>(), loaded: false,
  connection: "connecting" as ConnectionState,
});

export const useLive = create<LiveState>()((set, get) => ({
  ...initial(),

  hydrate(s) {
    const st = get();
    st.clock.sync(s.server_time);
    const seen = new Set(st.seen);
    const missed: Alert[] = [];
    const alerts: Record<number, Alert> = {};
    for (const a of s.alerts) {
      alerts[a.id] = a;
      // first load: history; later (re)loads: alerts that arrived while the stream was down
      if (st.loaded && !seen.has(a.id) && a.status === "new") missed.push(a);
      seen.add(a.id);
    }
    set({
      mission: s.mission, missions: s.missions, telemetry: s.telemetry,
      telemetryAt: s.link.age_s != null ? s.server_time - s.link.age_s : null,
      preview: s.preview, alerts, track: s.track.filter((p) => isNum(p.lat) && isNum(p.lon)),
      seen, loaded: true,
    });
    return missed;
  },

  applyEvent(name, data) {
    const st = get();
    if (data && isNum(data.server_time)) st.clock.sync(data.server_time);
    switch (name) {
      case "telemetry": {
        const t: Telemetry = data.telemetry ?? {};
        const g = t.gps;
        const track = g && g.fix === true && isNum(g.lat) && isNum(g.lon)
          ? [...st.track, { t: data.server_time, lat: g.lat, lon: g.lon, alt_m: isNum(g.alt_m) ? g.alt_m : null }]
          : st.track;
        set({ telemetry: t, telemetryAt: data.server_time ?? st.clock.now(), track });
        return {};
      }
      case "preview":
        set({ preview: { t: data.t, stage2: !!data.stage2 } });
        return {};
      case "alert": {
        const a: Alert = data.alert;
        if (!a || !st.mission || a.mission_id !== st.mission.id) return {};
        const isNew = !st.seen.has(a.id);
        const seen = isNew ? new Set(st.seen).add(a.id) : st.seen;
        set({ alerts: { ...st.alerts, [a.id]: a }, seen });
        return isNew ? { notify: a } : {};
      }
      case "alert_update": {
        const a: Alert = data.alert;
        if (a && st.alerts[a.id]) set({ alerts: { ...st.alerts, [a.id]: a } });
        return {};
      }
      default:
        return {};
    }
  },

  setConnection(c) { set({ connection: c }); },
  reset() { set(initial()); },
}));

export function linkState(s: Pick<LiveState, "telemetryAt">, nowS: number): LinkInfo {
  if (s.telemetryAt == null) return { state: "never", age_s: null };
  const age = Math.max(0, nowS - s.telemetryAt);
  return { state: age < LINK_LOST_S ? "live" : "lost", age_s: age };
}

export function alertVisible(a: Alert, p: Pick<Prefs, "types" | "status">): boolean {
  if (!p.types.includes(a.type)) return false;
  if (p.status === "all") return true;
  if (p.status === "open") return a.status !== "resolved";
  return a.status === p.status;
}

export function sortAlerts(list: Alert[]): Alert[] {
  return [...list].sort((a, b) =>
    (a.status === "resolved" ? 1 : 0) - (b.status === "resolved" ? 1 : 0)
    || PRIORITY[a.type] - PRIORITY[b.type] || b.id - a.id);
}

export function visibleAlerts(s: Pick<LiveState, "alerts">, p: Pick<Prefs, "types" | "status">): Alert[] {
  return sortAlerts(Object.values(s.alerts).filter((a) => alertVisible(a, p)));
}
