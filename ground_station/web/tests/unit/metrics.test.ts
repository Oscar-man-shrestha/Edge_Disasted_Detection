import { describe, expect, it } from "vitest";
import { detectionsPerMinute, summary } from "../../src/features/analytics/metrics";
import { alert, MISSION } from "../fixtures/data";
import { EMPTY, sample, timeline } from "../fixtures/timeline";

const S = MISSION.started_ts;

describe("analytics metrics", () => {
  it("detections per minute, zero-filled, null received_at counted at start", () => {
    const tl = timeline({
      mission: { ...MISSION, ended_ts: S + 100 }, telemetry: [sample(0), sample(100)],
      track: [], alerts: [alert(1, { type: "fire", received_at: S + 10 }), alert(2, { type: "person", received_at: S + 70 }),
        alert(3, { type: "person", received_at: S + 75 }), alert(4, { type: "smoke", received_at: null })],
    });
    expect(detectionsPerMinute(tl)).toEqual([
      { minute: 0, person: 0, fire: 1, smoke: 1 },
      { minute: 1, person: 2, fire: 0, smoke: 0 },
    ]);
  });
  it("summary numbers", () => {
    const s = summary(timeline());
    expect(s.distanceM).toBeCloseTo(111.32, 1);
    expect(s.durationS).toBe(120);
    expect(s.stage2Runs).toBe(10);
    expect(s.stage2Skipped).toBe(30);
    expect(s.computeSavedPct).toBe(75);
    expect(s.counts.fire).toEqual({ total: 1, open: 1 });
    expect(s.avgPowerW).toBeCloseTo(5, 6);
    expect(s.peakCpuC).toBe(50);
  });
  it("no power data gives null, not NaN", () => {
    const s = summary(timeline({ telemetry: [sample(0, { power_mw: null, cpu_temp_c: null, gpu_temp_c: null })] }));
    expect(s.avgPowerW).toBeNull();
    expect(s.peakPowerW).toBeNull();
    expect(s.peakCpuC).toBeNull();
  });
  it("empty mission has no NaN anywhere", () => {
    const s = summary(EMPTY);
    expect(s.durationS).toBe(0);
    expect(s.distanceM).toBe(0);
    expect(s.computeSavedPct).toBeNull();
    expect(JSON.stringify(s)).not.toMatch(/NaN|Infinity/);
    expect(detectionsPerMinute(EMPTY)).toEqual([{ minute: 0, person: 0, fire: 0, smoke: 0 }]);
  });
  it("10 000 samples and 1 000 alerts in under 50 ms", () => {
    const telemetry = Array.from({ length: 10_000 }, (_, i) => sample(i * 5, { stage2_runs: i, stage2_skipped: i * 2 }));
    const alerts = Array.from({ length: 1000 }, (_, i) => alert(i + 1, { received_at: S + i * 40 }));
    const track = telemetry.map((x) => ({ t: x.t, lat: x.lat!, lon: x.lon!, alt_m: null }));
    const tl = timeline({ mission: { ...MISSION, ended_ts: S + 50_000 }, telemetry, alerts, track });
    const t0 = performance.now();
    summary(tl); detectionsPerMinute(tl);
    expect(performance.now() - t0).toBeLessThan(50);
  });
});
