import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { Toaster } from "sonner";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { alert, state } from "../fixtures/data";

const updateAlert = vi.fn();
vi.mock("../../src/lib/api", async (orig) => ({ ...(await orig<typeof import("../../src/lib/api")>()), updateAlert: (...a: unknown[]) => updateAlert(...a) }));

const { AlertDetail } = await import("../../src/features/alerts/AlertDetail");
const { AlertList } = await import("../../src/features/alerts/AlertList");
const { useLive } = await import("../../src/store/live");

describe("alert workflow", () => {
  beforeEach(() => { updateAlert.mockReset(); useLive.getState().reset(); useLive.getState().hydrate(state()); });

  it("Acknowledge sends the status", async () => {
    updateAlert.mockResolvedValue(alert(1, { status: "acknowledged" }));
    render(<AlertDetail alert={alert(1)} onBack={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: "Acknowledge" }));
    await waitFor(() => expect(updateAlert).toHaveBeenCalledWith(1, { status: "acknowledged" }));
    await waitFor(() => expect(useLive.getState().alerts[1].status).toBe("acknowledged"));
  });

  it("Reopen on a resolved alert sends acknowledged", async () => {
    updateAlert.mockResolvedValue(alert(1, { status: "acknowledged" }));
    render(<AlertDetail alert={alert(1, { status: "resolved" })} onBack={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: "Reopen" }));
    await waitFor(() => expect(updateAlert).toHaveBeenCalledWith(1, { status: "acknowledged" }));
  });

  it("an API failure shows Update failed and keeps the status", async () => {
    updateAlert.mockRejectedValue(new Error("HTTP 500"));
    render(<><Toaster /><AlertDetail alert={alert(1)} onBack={() => {}} /></>);
    fireEvent.click(screen.getByRole("button", { name: "Resolve" }));
    expect(await screen.findByText(/Update failed/)).toBeInTheDocument();
    expect(useLive.getState().alerts[1].status).toBe("new");
  });

  it("no GPS fix: label and no Fly to", () => {
    render(<AlertDetail alert={alert(3, { lat: null, lon: null })} onBack={() => {}} />);
    expect(screen.getByText("no GPS fix")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /fly to/i })).toBeNull();
  });

  it("long lists render 200 rows then Show more", () => {
    const many = Array.from({ length: 500 }, (_, i) => alert(i + 1));
    const t0 = performance.now();
    const { container } = render(<AlertList alerts={many} selectedId={null} onSelect={() => {}} />);
    expect(performance.now() - t0).toBeLessThan(2000);
    expect(container.querySelectorAll("li")).toHaveLength(200);
    fireEvent.click(screen.getByText(/show more/i));
    expect(container.querySelectorAll("li")).toHaveLength(400);
  });
});
