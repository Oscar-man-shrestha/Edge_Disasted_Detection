import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const MapCtor = vi.fn();
vi.mock("maplibre-gl", () => ({ Map: MapCtor, Marker: vi.fn(), AttributionControl: vi.fn(), LngLatBounds: vi.fn() }));
vi.mock("../../src/features/map/webgl", () => ({ hasWebGL: () => false }));

describe("MissionMap without WebGL", () => {
  it("shows a notice and never constructs maplibre", async () => {
    const { MissionMap } = await import("../../src/features/map/MissionMap");
    render(<MissionMap mode="live" drone={null} trail={[]} alerts={[]} onSelectAlert={() => {}} />);
    expect(screen.getByText("Map needs WebGL")).toBeInTheDocument();
    expect(MapCtor).not.toHaveBeenCalled();
  });
});
