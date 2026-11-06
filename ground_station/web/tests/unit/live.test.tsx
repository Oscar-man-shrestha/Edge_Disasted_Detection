import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { CameraCard } from "../../src/features/live/CameraCard";
import { FlightHud } from "../../src/features/live/FlightHud";
import { useLive } from "../../src/store/live";
import { MISSION, state } from "../fixtures/data";

describe("live panels", () => {
  beforeEach(() => useLive.getState().reset());

  it("hot CPU shows a HOT label, not just a colour", () => {
    useLive.getState().hydrate(state({ telemetry: { system: { cpu_temp_c: 82, gpu_temp_c: 71 } } }));
    render(<FlightHud />);
    expect(screen.getByText("HOT")).toBeInTheDocument();
    expect(screen.getByText("WARM")).toBeInTheDocument();
  });

  it("null gps renders dashes without crashing", () => {
    useLive.getState().hydrate(state({ telemetry: { gps: null, pipeline: null, system: null } }));
    render(<FlightHud />);
    expect(screen.getByTestId("hud-speed")).toHaveTextContent("—");
  });

  it("stale preview after 5 s of server time", () => {
    useLive.getState().hydrate(state({ server_time: MISSION.started_ts + 600, preview: { t: MISSION.started_ts + 594, stage2: true } }));
    render(<CameraCard />);
    expect(screen.getByText("STALE")).toBeInTheDocument();
    expect(screen.queryByText("YOLO ACTIVE")).toBeNull();   // an old frame must not claim YOLO is running
  });
});

it("fresh preview with stage 2 shows YOLO ACTIVE", () => {
  useLive.getState().reset();
  useLive.getState().hydrate(state({ server_time: MISSION.started_ts + 600, preview: { t: MISSION.started_ts + 599.5, stage2: true } }));
  render(<CameraCard />);
  expect(screen.getByText("YOLO ACTIVE")).toBeInTheDocument();
  expect(screen.queryByText("STALE")).toBeNull();
});

describe("camera card: what the AI sees now", () => {
  it("shows a chip for every detected type while Stage 2 is active, none when idle", async () => {
    const { render: r, screen: sc } = await import("@testing-library/react");
    const { CameraCard } = await import("../../src/features/live/CameraCard");
    const { useLive: live } = await import("../../src/store/live");
    const { state: st } = await import("../fixtures/data");
    const base = st();
    const tel = (pipeline: any) => live.getState().hydrate({ ...base, telemetry: { ...base.telemetry!, pipeline } });
    tel({ state: "active", detections: [{ type: "person", conf: 0.9, t: 1 }, { type: "fire", conf: 0.72, t: 1 }] });
    const { unmount } = r(<CameraCard />);
    expect(sc.getByText("person 90%")).toBeInTheDocument();
    expect(sc.getByText("fire 72%")).toBeInTheDocument();
    unmount();
    tel({ state: "scanning", detections: [{ type: "fire", conf: 0.72, t: 1 }] });
    r(<CameraCard />);
    expect(sc.queryByText("fire 72%")).toBeNull();
  });
});
