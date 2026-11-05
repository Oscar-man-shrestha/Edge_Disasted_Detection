import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useAnimatedDrone } from "../../src/features/map/useAnimatedDrone";

let now = 0;
let frames: FrameRequestCallback[] = [];
function advance(ms: number) {
  now += ms;
  const run = frames; frames = [];
  act(() => run.forEach((f) => f(now)));
}

describe("useAnimatedDrone", () => {
  beforeEach(() => {
    now = 1000; frames = [];
    vi.spyOn(performance, "now").mockImplementation(() => now);
    vi.stubGlobal("requestAnimationFrame", (f: FrameRequestCallback) => { frames.push(f); return frames.length; });
    vi.stubGlobal("cancelAnimationFrame", () => {});
  });
  afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

  it("jumps to the first target, then glides to the next", () => {
    const { result, rerender } = renderHook(({ t }) => useAnimatedDrone(t, 1000), {
      initialProps: { t: { lat: 0, lon: 0, course: 350 } as any },
    });
    expect(result.current).toEqual({ lat: 0, lon: 0, course: 350 });
    rerender({ t: { lat: 2, lon: 4, course: 10 } });
    advance(500);
    expect(result.current!.lat).toBeCloseTo(1, 6);
    expect(result.current!.lon).toBeCloseTo(2, 6);
    expect(result.current!.course).toBeCloseTo(0, 6);
    advance(600);
    expect(result.current).toEqual({ lat: 2, lon: 4, course: 10 });
  });

  it("null target clears the pose", () => {
    const { result, rerender } = renderHook(({ t }) => useAnimatedDrone(t), { initialProps: { t: { lat: 1, lon: 1, course: null } as any } });
    rerender({ t: null });
    expect(result.current).toBeNull();
  });
});
