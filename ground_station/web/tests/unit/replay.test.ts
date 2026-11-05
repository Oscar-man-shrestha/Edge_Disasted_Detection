import { describe, expect, it } from "vitest";
import { alertsAt, alertTime, bounds, playback, segments, stateAt } from "../../src/features/replay/replay";
import { MISSION } from "../fixtures/data";
import { EMPTY, timeline } from "../fixtures/timeline";

const S = MISSION.started_ts;

describe("replay maths", () => {
  it("bounds span mission start to last data", () => {
    expect(bounds(timeline())).toEqual({ start: S, end: S + 120 });
    expect(bounds(EMPTY)).toEqual({ start: S, end: S });
  });
  it("alerts appear at their received time; null received_at pins to mission start", () => {
    const tl = timeline();
    expect(alertTime(tl.alerts[2], tl)).toBe(S);
    expect(alertsAt(tl, S - 1).map((a) => a.id)).toEqual([]);
    expect(alertsAt(tl, S).map((a) => a.id)).toEqual([3]);
    expect(alertsAt(tl, S + 10).map((a) => a.id).sort()).toEqual([1, 3]);
    expect(alertsAt(tl, S + 120)).toHaveLength(3);
  });
  it("stateAt interpolates the drone and cuts the trail at t", () => {
    const st = stateAt(timeline(), S + 25);
    expect(st.drone!.lat).toBeCloseTo(12.97025, 6);
    expect(st.sample!.t).toBe(S);
    expect(st.trail).toEqual([[77.59, 12.97]]);
    expect(stateAt(timeline(), S + 100).trail).toHaveLength(2);
    expect(stateAt(EMPTY, S)).toEqual({ drone: null, sample: null, trail: [] });
  });
  it("falls back to track points when telemetry has no position", () => {
    const tl = timeline({ telemetry: [] });
    expect(stateAt(tl, S + 50).drone!.lat).toBeCloseTo(12.9705, 6);
  });
  it("pipeline segments", () => {
    expect(segments(timeline())).toEqual([
      { start: S, end: S + 50, state: "scanning" }, { start: S + 50, end: S + 100, state: "active" },
      { start: S + 100, end: S + 120, state: "scanning" },
    ]);
    expect(segments(EMPTY)).toEqual([]);
  });
  it("playback reducer", () => {
    const b = { start: S, end: S + 120 };
    let p = playback.init(b);
    expect(p).toEqual({ t: S, playing: false, speed: 1 });
    p = playback.reduce(p, { type: "setSpeed", speed: 16 }, b);
    p = playback.reduce(p, { type: "play" }, b);
    p = playback.reduce(p, { type: "tick", dtMs: 1000 }, b);
    expect(p.t).toBe(S + 16);
    p = playback.reduce(p, { type: "tick", dtMs: 10_000 }, b);
    expect(p).toMatchObject({ t: S + 120, playing: false });
    p = playback.reduce(p, { type: "seek", t: S + 5 }, b);
    p = playback.reduce(p, { type: "step", by: -10 }, b);
    expect(p.t).toBe(S);
    p = playback.reduce(p, { type: "toggle" }, b);
    expect(p.playing).toBe(true);
  });
});
