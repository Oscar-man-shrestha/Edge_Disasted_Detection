import { act, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it } from "vitest";
import { AppShell } from "../../src/features/shell/AppShell";
import { ErrorBoundary } from "../../src/features/shell/ErrorBoundary";
import { useLive } from "../../src/store/live";
import { state } from "../fixtures/data";

function wrap(ui: React.ReactNode) {
  return <QueryClientProvider client={new QueryClient()}>{ui}</QueryClientProvider>;
}

describe("shell", () => {
  beforeEach(() => { useLive.getState().reset(); window.location.hash = "#/missions-test-reset"; });

  it("shows the link pill and routes by hash", async () => {
    useLive.getState().hydrate(state());
    window.location.hash = "#/missions";
    render(wrap(<AppShell />));
    expect(screen.getByTestId("link-pill")).toHaveTextContent("LIVE · nano");
    expect(await screen.findByRole("heading", { name: "Missions" })).toBeInTheDocument();
    act(() => { window.location.hash = "#/analytics"; window.dispatchEvent(new HashChangeEvent("hashchange")); });
    expect(await screen.findByRole("heading", { name: "Analytics" })).toBeInTheDocument();
  });

  it("error boundary isolates a crashing panel", () => {
    const Boom = () => { throw new Error("boom"); };
    const orig = console.error; console.error = () => {};
    render(<ErrorBoundary name="Camera"><Boom /></ErrorBoundary>);
    console.error = orig;
    expect(screen.getByText("This panel failed")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reload panel" })).toBeInTheDocument();
  });
});
