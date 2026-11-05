import { render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import { MISSION } from "../fixtures/data";

vi.mock("../../src/lib/api", async (orig) => ({
  ...(await orig<typeof import("../../src/lib/api")>()),
  getMissions: async () => [{ ...MISSION, alert_counts: { person: 1, fire: 2, smoke: 0 }, distance_m: 111.3 },
    { ...MISSION, id: 2, name: "Survey B", ended_ts: null }],
}));
const { default: MissionsView } = await import("../../src/features/missions/MissionsView");

describe("MissionsView", () => {
  it("lists missions with report and export links", async () => {
    render(<QueryClientProvider client={new QueryClient()}><MissionsView /></QueryClientProvider>);
    const row = (await screen.findByText("Survey B")).closest("tr")!;
    expect(within(row).getByRole("link", { name: /report/i })).toHaveAttribute("href", "/report/2");
    expect(within(row).getByRole("link", { name: "CSV" })).toHaveAttribute("href", "/api/missions/2/export.csv");
    const first = screen.getByText("Mission 1").closest("tr")!;
    expect(first).toHaveTextContent("111 m");
    expect(screen.getByRole("heading", { name: "Missions" })).toBeInTheDocument();
  });
});
