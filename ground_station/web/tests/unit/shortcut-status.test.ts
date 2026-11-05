import { describe, expect, it } from "vitest";
import { shortcutStatus } from "../../src/features/shell/AppShell";
import { alert } from "../fixtures/data";

describe("A / R shortcuts never silently reopen", () => {
  it("A acknowledges only new alerts", () => {
    expect(shortcutStatus(alert(1, { status: "new" }), "a")).toBe("acknowledged");
    expect(shortcutStatus(alert(1, { status: "acknowledged" }), "a")).toBeNull();
    expect(shortcutStatus(alert(1, { status: "resolved" }), "a")).toBeNull();
  });
  it("R resolves anything not yet resolved", () => {
    expect(shortcutStatus(alert(1, { status: "new" }), "r")).toBe("resolved");
    expect(shortcutStatus(alert(1, { status: "acknowledged" }), "r")).toBe("resolved");
    expect(shortcutStatus(alert(1, { status: "resolved" }), "r")).toBeNull();
    expect(shortcutStatus(undefined, "r")).toBeNull();
  });
});
