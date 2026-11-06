export type AlertType = "person" | "fire" | "smoke";
export type AlertStatus = "new" | "acknowledged" | "resolved";
export type AlertStatusFilter = "open" | "all" | AlertStatus;
export const ALERT_TYPES: AlertType[] = ["person", "fire", "smoke"];
export const PRIORITY: Record<AlertType, number> = { person: 1, fire: 2, smoke: 3 };

export interface Alert {
  id: number; mission_id: number; drone_id: string | null; type: AlertType; conf: number;
  lat: number | null; lon: number | null; wall_time: string | null; received: string | null;
  received_at: number | null; snapshot: string | null; status: AlertStatus; note: string | null;
  acked_at: string | null; resolved_at: string | null;
  /** short clip around the alert (JPEG frames), when the drone sent one */
  clip_frames?: number | null; clip_fps?: number | null;
}
export interface Mission {
  id: number; name: string; started_at: string; ended_at: string | null;
  started_ts: number; ended_ts: number | null;
  alert_counts?: Record<AlertType, number>; distance_m?: number;
}
export interface Gps {
  mode?: string; fix?: boolean | null; lat?: number | null; lon?: number | null; alt_m?: number | null;
  sats?: number | null; hdop?: number | null; speed_mps?: number | null; course_deg?: number | null; age_s?: number | null;
  /** simulated GPS only: who is flying it */
  control?: "auto" | "manual" | "return";
}
export interface Pipeline {
  state?: "idle" | "scanning" | "active"; fps?: number | null; frames?: number; stage1_ms?: number | null;
  stage2_ms?: number | null; stage2_runs?: number; stage2_skipped?: number; triggers?: number;
  last_detection?: { type: AlertType; conf: number; t: number } | null;
}
export interface SystemStats {
  power_mw?: number | null; cpu_temp_c?: number | null; gpu_temp_c?: number | null;
  cpu_load_pct?: number | null; gpu_load_pct?: number | null; ram_used_mb?: number | null; ram_total_mb?: number | null;
}
export interface Telemetry {
  drone_id?: string | null; seq?: number; time?: number; uptime_s?: number; gps?: Gps | null;
  pipeline?: Pipeline | null; system?: SystemStats | null;
  link?: { alerts_buffered?: number; alerts_sent?: number } | null;
}
export interface TrackPoint { t: number; lat: number; lon: number; alt_m: number | null }
export interface TelemetrySample {
  t: number; lat: number | null; lon: number | null; alt_m: number | null; speed_mps: number | null;
  course_deg: number | null; sats: number | null; fix: number | null; fps: number | null; state: string | null;
  stage2_runs: number | null; stage2_skipped: number | null; power_mw: number | null;
  cpu_temp_c: number | null; gpu_temp_c: number | null; cpu_load_pct: number | null; gpu_load_pct: number | null;
}
export interface LinkInfo { state: "live" | "lost" | "never"; age_s: number | null }
export interface Preview { t: number; frame_t?: number | null; stage2: boolean }
export interface StateResponse {
  server_time: number; mission: Mission; missions: Mission[]; link: LinkInfo;
  telemetry: Telemetry | null; preview: Preview | null; alerts: Alert[]; track: TrackPoint[];
}
export interface Timeline {
  mission: Mission; server_time: number; track: TrackPoint[]; telemetry: TelemetrySample[]; alerts: Alert[];
}
