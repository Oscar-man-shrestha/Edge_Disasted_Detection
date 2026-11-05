import type { Alert, Mission, StateResponse } from "../../src/lib/types";

export const MISSION: Mission = {
  id: 1, name: "Mission 1", started_at: "2026-11-05 10:00:00", ended_at: null,
  started_ts: 1_793_000_000, ended_ts: null,
};

export function alert(id: number, over: Partial<Alert> = {}): Alert {
  return {
    id, mission_id: 1, drone_id: "nano", type: "fire", conf: 0.8, lat: 12.97, lon: 77.59,
    wall_time: "2026-11-05 10:01:00", received: "10:01:00", received_at: MISSION.started_ts + 60 * id,
    snapshot: `${id}_fire.jpg`, status: "new", note: null, acked_at: null, resolved_at: null, ...over,
  };
}

export function state(over: Partial<StateResponse> = {}): StateResponse {
  return {
    server_time: MISSION.started_ts + 600, mission: MISSION, missions: [MISSION],
    link: { state: "live", age_s: 0.5 },
    telemetry: { drone_id: "nano", gps: { fix: true, lat: 12.97, lon: 77.59, sats: 9, hdop: 0.9 },
                 pipeline: { state: "scanning", fps: 2 }, system: { power_mw: 5000 } },
    preview: { t: MISSION.started_ts + 599, stage2: false },
    alerts: [alert(1), alert(2, { type: "person", status: "acknowledged" })],
    track: [{ t: MISSION.started_ts + 500, lat: 12.97, lon: 77.59, alt_m: null }],
    ...over,
  };
}
