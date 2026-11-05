import { describe, expect, it } from "vitest";
import { ALERT_SOURCE_LAYER, alertSourceLayer } from "../../src/features/map/mapStyle";

describe("clustered alert source", () => {
  it("has an invisible layer so MapLibre loads its tiles (querySourceFeatures needs one)", () => {
    const l = alertSourceLayer() as any;
    expect(l.id).toBe(ALERT_SOURCE_LAYER);
    expect(l.source).toBe("alerts");
    expect(l.type).toBe("circle");
    expect(l.paint["circle-opacity"]).toBe(0);
    expect(l.paint["circle-radius"]).toBe(0);
  });
});
