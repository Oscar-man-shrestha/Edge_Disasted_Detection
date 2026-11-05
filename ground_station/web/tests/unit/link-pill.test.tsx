import { act, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LinkPill } from "../../src/features/shell/LinkPill";
import { useLive } from "../../src/store/live";
import { state } from "../fixtures/data";

describe("LinkPill announcements", () => {
  beforeEach(() => { vi.useFakeTimers(); useLive.getState().reset(); });
  it("the ticking pill is not a live region; only state changes are announced", () => {
    useLive.getState().hydrate(state());
    render(<LinkPill />);
    const pill = screen.getByTestId("link-pill");
    expect(pill).not.toHaveAttribute("aria-live");
    const region = screen.getByTestId("link-announcer");
    expect(region).toHaveAttribute("aria-live", "polite");
    expect(region).toHaveTextContent("Drone link live");
    act(() => { vi.advanceTimersByTime(5000); });             // link goes lost, age keeps ticking
    expect(pill).toHaveTextContent(/LINK LOST/);
    const first = region.textContent;
    act(() => { vi.advanceTimersByTime(3000); });
    expect(region.textContent).toBe(first);                   // no per-second re-announcement
    expect(region).toHaveTextContent("Drone link lost");
    vi.useRealTimers();
  });
});
