import { pathDistanceM } from "../../lib/geo";
import { ALERT_TYPES, type AlertType, type Timeline } from "../../lib/types";
import { alertTime, bounds } from "../replay/replay";

export interface MinuteBucket { minute: number; person: number; fire: number; smoke: number }

export function detectionsPerMinute(tl: Timeline): MinuteBucket[] {
  const b = bounds(tl);
  const n = Math.floor((b.end - b.start) / 60) + 1;
  const out: MinuteBucket[] = Array.from({ length: n }, (_, minute) => ({ minute, person: 0, fire: 0, smoke: 0 }));
  for (const a of tl.alerts) {
    const m = Math.min(n - 1, Math.max(0, Math.floor((alertTime(a, tl) - b.start) / 60)));
    out[m][a.type]++;
  }
  return out;
}

export interface Summary {
  durationS: number; distanceM: number;
  counts: Record<AlertType, { total: number; open: number }>;
  stage2Runs: number | null; stage2Skipped: number | null; computeSavedPct: number | null;
  avgPowerW: number | null; peakPowerW: number | null; peakCpuC: number | null; peakGpuC: number | null;
}

const fin = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);

export function summary(tl: Timeline): Summary {
  const b = bounds(tl);
  const counts = Object.fromEntries(ALERT_TYPES.map((t) => [t, { total: 0, open: 0 }])) as Summary["counts"];
  for (const a of tl.alerts) { counts[a.type].total++; if (a.status !== "resolved") counts[a.type].open++; }
  let runs: number | null = null, skipped: number | null = null;
  let pSum = 0, pN = 0, pMax: number | null = null, cMax: number | null = null, gMax: number | null = null;
  for (const s of tl.telemetry) {
    if (fin(s.stage2_runs)) runs = s.stage2_runs;
    if (fin(s.stage2_skipped)) skipped = s.stage2_skipped;
    if (fin(s.power_mw)) { const w = s.power_mw / 1000; pSum += w; pN++; pMax = pMax == null ? w : Math.max(pMax, w); }
    if (fin(s.cpu_temp_c)) cMax = cMax == null ? s.cpu_temp_c : Math.max(cMax, s.cpu_temp_c);
    if (fin(s.gpu_temp_c)) gMax = gMax == null ? s.gpu_temp_c : Math.max(gMax, s.gpu_temp_c);
  }
  const total = (runs ?? 0) + (skipped ?? 0);
  return {
    durationS: b.end - b.start, distanceM: pathDistanceM(tl.track), counts,
    stage2Runs: runs, stage2Skipped: skipped,
    computeSavedPct: total > 0 ? Math.round(((skipped ?? 0) / total) * 1000) / 10 : null,
    avgPowerW: pN ? pSum / pN : null, peakPowerW: pMax, peakCpuC: cMax, peakGpuC: gMax,
  };
}
