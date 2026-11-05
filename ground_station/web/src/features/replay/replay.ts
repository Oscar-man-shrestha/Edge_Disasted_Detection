import { interpolateAt, type DronePose } from "../../lib/geo";
import type { Alert, TelemetrySample, Timeline } from "../../lib/types";

export interface Bounds { start: number; end: number }

export function bounds(tl: Timeline): Bounds {
  const start = tl.mission.started_ts;
  const ends = [tl.mission.ended_ts ?? start, start];
  if (tl.telemetry.length) ends.push(tl.telemetry[tl.telemetry.length - 1].t);
  if (tl.track.length) ends.push(tl.track[tl.track.length - 1].t);
  for (const a of tl.alerts) if (a.received_at != null) ends.push(a.received_at);
  return { start, end: Math.max(...ends) };
}

/** When an alert "happened" for replay: station receive time; v2 alerts without one pin to mission start. */
export function alertTime(a: Alert, tl: Timeline): number {
  return a.received_at ?? tl.mission.started_ts;
}

export function alertsAt(tl: Timeline, t: number): Alert[] {
  return tl.alerts.filter((a) => alertTime(a, tl) <= t);
}

export interface ReplayState { drone: DronePose | null; sample: TelemetrySample | null; trail: [number, number][] }

export function stateAt(tl: Timeline, t: number): ReplayState {
  const fromTelemetry = interpolateAt(tl.telemetry, t);
  const drone = fromTelemetry ?? interpolateAt(tl.track.map((p) => ({ ...p, course_deg: null })), t);
  let sample: TelemetrySample | null = null;
  for (const s of tl.telemetry) { if (s.t <= t) sample = s; else break; }
  if (!sample && tl.telemetry.length) sample = tl.telemetry[0];
  const trail = tl.track.filter((p) => p.t <= t).map((p) => [p.lon, p.lat] as [number, number]);
  return { drone, sample, trail };
}

export interface Segment { start: number; end: number; state: string }

/** Pipeline-state band: consecutive samples with the same state merged. */
export function segments(tl: Timeline): Segment[] {
  const out: Segment[] = [];
  const end = bounds(tl).end;
  tl.telemetry.forEach((s, i) => {
    const next = tl.telemetry[i + 1]?.t ?? end;
    const state = s.state ?? "idle";
    const last = out[out.length - 1];
    if (last && last.state === state) last.end = next;
    else out.push({ start: s.t, end: next, state });
  });
  return out.filter((s) => s.end > s.start);
}

// ---------------------------------------------------------------- playback
export type Speed = 1 | 4 | 16;
export interface PlayState { t: number; playing: boolean; speed: Speed }
export type PlayAction =
  | { type: "play" } | { type: "pause" } | { type: "toggle" }
  | { type: "seek"; t: number } | { type: "step"; by: number }
  | { type: "setSpeed"; speed: Speed } | { type: "tick"; dtMs: number };

const clamp = (t: number, b: Bounds) => Math.min(b.end, Math.max(b.start, t));

export const playback = {
  init: (b: Bounds): PlayState => ({ t: b.start, playing: false, speed: 1 }),
  reduce(s: PlayState, a: PlayAction, b: Bounds): PlayState {
    switch (a.type) {
      case "play": return { ...s, playing: true, t: s.t >= b.end ? b.start : s.t };
      case "pause": return { ...s, playing: false };
      case "toggle": return playback.reduce(s, { type: s.playing ? "pause" : "play" }, b);
      case "seek": return { ...s, t: clamp(a.t, b) };
      case "step": return { ...s, t: clamp(s.t + a.by, b) };
      case "setSpeed": return { ...s, speed: a.speed };
      case "tick": {
        const t = clamp(s.t + (a.dtMs / 1000) * s.speed, b);
        return { ...s, t, playing: s.playing && t < b.end };
      }
    }
  },
};
