import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import { MISSION } from "../fixtures/data";
import { EMPTY, timeline } from "../fixtures/timeline";

vi.mock("../../src/features/map/MissionMap", () => ({ MissionMap: (p: any) => <div data-testid="map">{p.alerts.length} alerts</div> }));
const getTimeline = vi.fn();
vi.mock("../../src/lib/api", async (orig) => ({
  ...(await orig<typeof import("../../src/lib/api")>()),
  getTimeline: (id: number) => getTimeline(id),
  getMissions: async () => [MISSION],
}));
const { default: ReplayView } = await import("../../src/features/replay/ReplayView");

function renderView() {
  return render(<QueryClientProvider client={new QueryClient()}><ReplayView missionId={1} /></QueryClientProvider>);
}

describe("ReplayView", () => {
  it("clicking an alert tick seeks the playhead to that alert", async () => {
    getTimeline.mockResolvedValue(timeline());
    renderView();
    const slider = await screen.findByRole("slider", { name: "Replay time" });
    expect((slider as HTMLInputElement).value).toBe("0");
    fireEvent.click(screen.getByRole("button", { name: /person alert #2/i }));
    expect((slider as HTMLInputElement).value).toBe("70");
    expect(screen.getByTestId("map")).toHaveTextContent("3 alerts");
  });
  it("empty mission shows an empty state", async () => {
    getTimeline.mockResolvedValue(EMPTY);
    renderView();
    expect(await screen.findByText("No flight data recorded for this mission")).toBeInTheDocument();
  });
});
