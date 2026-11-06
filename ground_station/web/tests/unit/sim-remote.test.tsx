import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { state } from "../fixtures/data";

const simControl = vi.fn();
vi.mock("../../src/lib/api", async (orig) => ({ ...(await orig<typeof import("../../src/lib/api")>()), simControl: (...a: unknown[]) => simControl(...a) }));
const { SimRemote } = await import("../../src/features/live/SimRemote");
const { useLive } = await import("../../src/store/live");

const withGps = (gps: any) => {
  const s = state();
  useLive.getState().hydrate({ ...s, telemetry: { ...s.telemetry!, gps } });
};

describe("simulator remote", () => {
  beforeEach(() => { simControl.mockReset(); simControl.mockResolvedValue({ ok: true }); useLive.getState().reset(); });

  it("is hidden for a real GPS", () => {
    withGps({ mode: "nmea", fix: true, lat: 1, lon: 2 });
    const { container } = render(<SimRemote />);
    expect(container).toBeEmptyDOMElement();
  });

  it("taking over starts from the drone's own heading and speed; buttons steer", async () => {
    withGps({ mode: "sim", fix: true, lat: 1, lon: 2, course_deg: 178.6, speed_mps: 5, control: "auto" });
    render(<SimRemote />);
    expect(screen.getByText("Auto patrol", { selector: "span" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Manual" }));
    expect(simControl).toHaveBeenLastCalledWith({ mode: "manual", heading: 179, speed: 5 });
    fireEvent.click(screen.getByRole("button", { name: "Turn right" }));
    expect(simControl).toHaveBeenLastCalledWith({ mode: "manual", heading: 194, speed: 5 });
    fireEvent.click(screen.getByRole("button", { name: "Faster" }));
    expect(simControl).toHaveBeenLastCalledWith({ mode: "manual", heading: 194, speed: 6 });
    fireEvent.click(screen.getByRole("button", { name: "Hover" }));
    expect(simControl).toHaveBeenLastCalledWith({ mode: "manual", heading: 194, speed: 0 });
    expect(screen.getByRole("button", { name: "Slower" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Auto patrol" }));
    expect(simControl).toHaveBeenLastCalledWith({ mode: "auto" });
    await waitFor(() => expect(screen.queryByRole("button", { name: "Turn left" })).toBeNull());
  });

  it("arrow keys steer in manual; heading wraps through north", () => {
    withGps({ mode: "sim", fix: true, lat: 1, lon: 2, course_deg: 5, speed_mps: 5 });
    render(<SimRemote />);
    fireEvent.click(screen.getByRole("button", { name: "Manual" }));
    fireEvent.keyDown(window, { key: "ArrowLeft" });
    expect(simControl).toHaveBeenLastCalledWith({ mode: "manual", heading: 350, speed: 5 });
    fireEvent.keyDown(window, { key: "ArrowUp" });
    expect(simControl).toHaveBeenLastCalledWith({ mode: "manual", heading: 350, speed: 6 });
    fireEvent.keyDown(window, { key: " " });
    expect(simControl).toHaveBeenLastCalledWith({ mode: "manual", heading: 350, speed: 0 });
  });
});

describe("simulator remote, fast presses", () => {
  beforeEach(() => { simControl.mockReset(); simControl.mockResolvedValue({ ok: true }); useLive.getState().reset(); });
  it("three quick turns add up", () => {
    withGps({ mode: "sim", fix: true, lat: 1, lon: 2, course_deg: 0, speed_mps: 5 });
    render(<SimRemote />);
    fireEvent.click(screen.getByRole("button", { name: "Manual" }));
    const h = window.addEventListener; void h;
    const ev = () => new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true });
    window.dispatchEvent(ev()); window.dispatchEvent(ev()); window.dispatchEvent(ev());   // no re-render in between
    expect(simControl).toHaveBeenLastCalledWith({ mode: "manual", heading: 45, speed: 5 });
  });
});
