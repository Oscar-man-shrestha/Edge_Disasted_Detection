import type { Telemetry, TelemetrySample, Timeline } from "../../src/lib/types";
import { alert, MISSION } from "./data";

const S = MISSION.started_ts;

export function sample(dt: number, over: Partial<TelemetrySample> = {}): TelemetrySample {
  return { t: S + dt, lat: 12.97 + dt * 0.00001, lon: 77.59, alt_m: 900, speed_mps: 5, course_deg: 0, sats: 9, fix: 1,
    fps: 2, state: "scanning", stage2_runs: 0, stage2_skipped: 0, power_mw: 5000, cpu_temp_c: 50, gpu_temp_c: 48,
    cpu_load_pct: 40, gpu_load_pct: 10, ...over };
}

export function timeline(over: Partial<Timeline> = {}): Timeline {
  return {
    mission: { ...MISSION, ended_ts: S + 120 }, server_time: S + 200,
    track: [{ t: S, lat: 12.97, lon: 77.59, alt_m: null }, { t: S + 100, lat: 12.971, lon: 77.59, alt_m: null }],
    telemetry: [sample(0), sample(50, { state: "active", stage2_runs: 4, stage2_skipped: 6 }), sample(100, { stage2_runs: 10, stage2_skipped: 30 })],
    alerts: [alert(1, { received_at: S + 10 }), alert(2, { type: "person", received_at: S + 70 }), alert(3, { type: "smoke", received_at: null })],
    ...over,
  };
}

export const EMPTY: Timeline = { mission: { ...MISSION, ended_ts: null }, server_time: S, track: [], telemetry: [], alerts: [] };
export type { Telemetry };
