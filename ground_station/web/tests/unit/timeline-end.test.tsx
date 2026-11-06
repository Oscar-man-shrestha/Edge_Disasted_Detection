import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Timeline } from "../../src/features/replay/Timeline";
import { alertsAt } from "../../src/features/replay/replay";
import { alert, MISSION } from "../fixtures/data";

describe("replay slider end", () => {
  it("dragging to the end reaches the real end, so the newest alert is shown", () => {
    const start = MISSION.started_ts;
    const last = alert(2, { received_at: start + 15.3 });                    // newest event at 15.3 s
    const tl: any = { mission: MISSION, alerts: [alert(1, { received_at: start + 4 }), last], telemetry: [], track: [] };
    const b = { start, end: start + 15.3 };
    const onSeek = vi.fn();
    render(<Timeline tl={tl} b={b} t={start} onSeek={onSeek} />);
    const slider = screen.getByRole("slider", { name: "Replay time" });
    fireEvent.change(slider, { target: { value: slider.getAttribute("max") } });
    const t = onSeek.mock.calls.at(-1)![0];
    expect(t).toBe(b.end);
    expect(alertsAt(tl, t).map((a) => a.id)).toEqual([1, 2]);
  });
});
