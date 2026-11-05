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
