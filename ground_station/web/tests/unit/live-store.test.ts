import { beforeEach, describe, expect, it } from "vitest";
import { createClock } from "../../src/lib/clock";
import { DEFAULT_PREFS } from "../../src/lib/prefs";
import { linkState, useLive, visibleAlerts } from "../../src/store/live";
import { alert, MISSION, state } from "../fixtures/data";

const reset = () => useLive.getState().reset();

describe("live store", () => {
  beforeEach(reset);

  it("first hydrate marks everything seen and returns no missed alerts", () => {
    expect(useLive.getState().hydrate(state())).toEqual([]);
    expect(useLive.getState().seen.has(1)).toBe(true);
    expect(useLive.getState().loaded).toBe(true);
  });

  it("a later hydrate returns new alerts that arrived while disconnected", () => {
    useLive.getState().hydrate(state());
    const later = state({ alerts: [alert(1), alert(3), alert(4, { status: "resolved" })] });
    const missed = useLive.getState().hydrate(later);
    expect(missed.map((a) => a.id)).toEqual([3]);
    expect(useLive.getState().hydrate(later)).toEqual([]);
  });

  it("alert events: other missions ignored, first sight notifies once", () => {
    useLive.getState().hydrate(state());
    const other = useLive.getState().applyEvent("alert", { alert: alert(9, { mission_id: 2 }), server_time: 1 });
    expect(other.notify).toBeUndefined();
    expect(useLive.getState().alerts[9]).toBeUndefined();
    const first = useLive.getState().applyEvent("alert", { alert: alert(5), server_time: 1 });
    expect(first.notify?.id).toBe(5);
    const again = useLive.getState().applyEvent("alert", { alert: alert(5), server_time: 1 });
    expect(again.notify).toBeUndefined();
  });

  it("alert_update replaces a known alert only", () => {
    useLive.getState().hydrate(state());
    useLive.getState().applyEvent("alert_update", { alert: alert(1, { status: "resolved" }) });
    expect(useLive.getState().alerts[1].status).toBe("resolved");
    useLive.getState().applyEvent("alert_update", { alert: alert(77) });
    expect(useLive.getState().alerts[77]).toBeUndefined();
  });

  it("telemetry events update link time and track only with a finite fix", () => {
    useLive.getState().hydrate(state({ track: [] }));
    useLive.getState().applyEvent("telemetry", { telemetry: { gps: { fix: true, lat: null, lon: 1 } }, server_time: MISSION.started_ts + 700 });
    expect(useLive.getState().track).toHaveLength(0);
    expect(useLive.getState().telemetryAt).toBe(MISSION.started_ts + 700);
    useLive.getState().applyEvent("telemetry", { telemetry: { gps: { fix: true, lat: 12.97, lon: 77.59 } }, server_time: MISSION.started_ts + 701 });
    expect(useLive.getState().track).toHaveLength(1);
  });

  it("preview event sets preview", () => {
    useLive.getState().hydrate(state());
    useLive.getState().applyEvent("preview", { t: 123, stage2: true, server_time: 123 });
    expect(useLive.getState().preview).toEqual({ t: 123, stage2: true });
  });

  it("linkState uses server time even if the browser clock is hours off", () => {
    let local = (MISSION.started_ts - 3 * 3600) * 1000; // browser 3 h behind
    const clock = createClock(() => local);
    clock.sync(MISSION.started_ts, local);
    const s = { ...useLive.getState(), telemetryAt: MISSION.started_ts };
    local += 2900;
    expect(linkState(s, clock.now()).state).toBe("live");
    local += 200;
    expect(linkState(s, clock.now()).state).toBe("lost");
    expect(linkState({ ...s, telemetryAt: null }, clock.now()).state).toBe("never");
  });

  it("visibleAlerts: open filter, type filter, ordering", () => {
    useLive.getState().hydrate(state({ alerts: [
      alert(1, { type: "smoke" }), alert(2, { type: "person" }), alert(3, { type: "fire" }),
      alert(4, { type: "person", status: "resolved" }), alert(5, { type: "fire" }),
    ] }));
    const s = useLive.getState();
    expect(visibleAlerts(s, DEFAULT_PREFS).map((a) => a.id)).toEqual([2, 5, 3, 1]);
    expect(visibleAlerts(s, { ...DEFAULT_PREFS, status: "all" }).map((a) => a.id)).toEqual([2, 5, 3, 1, 4]);
    expect(visibleAlerts(s, { ...DEFAULT_PREFS, types: ["fire"] }).map((a) => a.id)).toEqual([5, 3]);
  });
});

describe("resync merge", () => {
  beforeEach(reset);
  it("keeps alerts that arrived over SSE after the snapshot was taken", () => {
    useLive.getState().hydrate(state());                                    // alerts 1, 2
    useLive.getState().applyEvent("alert", { alert: alert(50), server_time: 1 });
    // an older snapshot (taken before alert 50 existed) arrives late
    useLive.getState().hydrate(state());
    expect(useLive.getState().alerts[50]).toBeDefined();
    expect(Object.keys(useLive.getState().alerts).map(Number).sort((a, b) => a - b)).toEqual([1, 2, 50]);
  });
  it("still drops alerts of another mission after a mission change", () => {
    useLive.getState().hydrate(state());
    useLive.getState().applyEvent("alert", { alert: alert(50), server_time: 1 });
    const m2 = { ...state().mission, id: 2 };
    useLive.getState().hydrate(state({ mission: m2, alerts: [] }));
    expect(useLive.getState().alerts[50]).toBeUndefined();
  });
});
