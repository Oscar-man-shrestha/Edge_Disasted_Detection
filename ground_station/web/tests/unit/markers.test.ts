import { describe, expect, it } from "vitest";
import { alertElement, updateAlertElement } from "../../src/features/map/markers";
import { alert } from "../fixtures/data";

describe("alert markers", () => {
  it("updating a marker keeps MapLibre's own classes (they position it on the map)", () => {
    const el = alertElement(alert(1), false, () => {});
    el.classList.add("maplibregl-marker", "maplibregl-marker-anchor-center");   // what MapLibre adds
    updateAlertElement(el, alert(1, { status: "acknowledged" }), true, () => {});
    expect(el.classList.contains("maplibregl-marker")).toBe(true);
    expect(el.classList.contains("maplibregl-marker-anchor-center")).toBe(true);
    expect(el.classList.contains("gs-amark-acknowledged")).toBe(true);
    expect(el.classList.contains("gs-amark-new")).toBe(false);
    expect(el.classList.contains("gs-amark-selected")).toBe(true);
  });

  it("changing type swaps the icon and the type class", () => {
    const el = alertElement(alert(2, { type: "fire" }), false, () => {});
    const fireIcon = el.innerHTML;
    updateAlertElement(el, alert(2, { type: "person" }), false, () => {});
    expect(el.innerHTML).not.toBe(fireIcon);
    expect(el.classList.contains("gs-amark-person")).toBe(true);
    expect(el.classList.contains("gs-amark-fire")).toBe(false);
    expect(el.getAttribute("aria-label")).toMatch(/^person alert 2/);
  });
});
