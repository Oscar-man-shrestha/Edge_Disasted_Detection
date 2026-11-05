import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import { MISSION } from "../fixtures/data";
import { EMPTY, timeline } from "../fixtures/timeline";

vi.mock("../../src/features/analytics/echarts", () => ({ useEChart: () => {} }));
const getTimeline = vi.fn();
vi.mock("../../src/lib/api", async (orig) => ({
  ...(await orig<typeof import("../../src/lib/api")>()),
  getTimeline: (id: number) => getTimeline(id), getMissions: async () => [MISSION],
}));
const { default: AnalyticsView } = await import("../../src/features/analytics/AnalyticsView");
const view = () => render(<QueryClientProvider client={new QueryClient()}><AnalyticsView missionId={1} /></QueryClientProvider>);

describe("AnalyticsView", () => {
  it("shows the compute saving KPI", async () => {
    getTimeline.mockResolvedValue(timeline());
    view();
    const tile = await screen.findByTestId("kpi-compute-saved");
    expect(tile).toHaveTextContent("75%");
    expect(screen.getByRole("heading", { name: "Analytics" })).toBeInTheDocument();
  });
  it("empty mission shows an empty state", async () => {
    getTimeline.mockResolvedValue(EMPTY);
    view();
    expect(await screen.findByText("No telemetry recorded for this mission")).toBeInTheDocument();
  });
});
