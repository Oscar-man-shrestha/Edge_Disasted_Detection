import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { CommandPalette } from "../../src/features/shell/CommandPalette";
import { useMapCommand, useOverlays } from "../../src/store/ui";

describe("command palette: go to coordinates", () => {
  beforeEach(() => {
    window.location.hash = "#/missions";
    useOverlays.getState().set({ palette: true });
    useMapCommand.setState({ cmd: null });
  });

  it("typed coordinates offer Go to, which flies the live map there", () => {
    render(<CommandPalette />);
    fireEvent.change(screen.getByPlaceholderText(/Type a command or search/), { target: { value: "12.9716, 77.5946" } });
    const go = screen.getByRole("option", { name: /Go to/ });
    expect(go).toHaveTextContent("12.971600, 77.594600");
    fireEvent.click(go);
    expect(useMapCommand.getState().cmd).toMatchObject({ type: "goto", lat: 12.9716, lon: 77.5946 });
    expect(window.location.hash).toBe("#/live");
    expect(useOverlays.getState().palette).toBe(false);
  });

  it("normal text shows no coordinate option", () => {
    render(<CommandPalette />);
    fireEvent.change(screen.getByPlaceholderText(/Type a command or search/), { target: { value: "export" } });
    expect(screen.queryByRole("option", { name: /Go to/ })).toBeNull();
  });
});
