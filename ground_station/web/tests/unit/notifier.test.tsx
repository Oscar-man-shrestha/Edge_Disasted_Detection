import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Notifier } from "../../src/features/shell/Notifier";
import { emitNewAlert } from "../../src/store/notify";
import { useLive } from "../../src/store/live";
import { usePrefs } from "../../src/store/ui";
import { alert, state } from "../fixtures/data";

const started: number[] = [];
class FakeOsc { frequency = { value: 0 }; type = "sine"; connect() { return { connect() {} }; } start() { started.push(this.frequency.value); } stop() {} }
class FakeGain { gain = { setValueAtTime() {}, exponentialRampToValueAtTime() {} }; connect() { return { connect() {} }; } }
class FakeAudio { currentTime = 0; state = "running"; destination = {}; createOscillator() { return new FakeOsc(); } createGain() { return new FakeGain(); } resume() {} }

describe("Notifier", () => {
  beforeEach(() => {
    started.length = 0;
    vi.stubGlobal("AudioContext", FakeAudio);
    useLive.getState().reset();
    usePrefs.getState().set({ mute: false });
    useLive.getState().hydrate(state({ alerts: [] }));
  });
  afterEach(() => vi.unstubAllGlobals());

  it("toasts, beeps, sets the title and shows the person banner until acknowledged", async () => {
    render(<Notifier />);
    const p = alert(10, { type: "person", conf: 0.91 });
    act(() => { useLive.getState().applyEvent("alert", { alert: p, server_time: 1 }); emitNewAlert(p); });
    expect(await screen.findByText(/New person alert/)).toBeInTheDocument();
    expect(document.title.startsWith("(1) New alerts")).toBe(true);
    expect(screen.getByRole("alert", { name: /person detected/i })).toBeInTheDocument();
    expect(started).toEqual([880, 660]);
    act(() => { useLive.getState().applyEvent("alert_update", { alert: { ...p, status: "acknowledged" } }); });
    expect(screen.queryByRole("alert", { name: /person detected/i })).toBeNull();
    expect(document.title).toBe("Ground Station");
  });

  it("muted: no oscillator", () => {
    usePrefs.getState().set({ mute: true });
    render(<Notifier />);
    act(() => emitNewAlert(alert(11)));
    expect(started).toEqual([]);
  });
});
