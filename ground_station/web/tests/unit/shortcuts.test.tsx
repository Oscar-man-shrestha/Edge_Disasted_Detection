import { fireEvent, render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useShortcuts } from "../../src/hooks/useShortcuts";

function Harness({ map }: { map: Record<string, () => void> }) {
  useShortcuts(map);
  return <input aria-label="field" />;
}

describe("useShortcuts", () => {
  it("fires on the body, not while typing; mod+k works from inputs", () => {
    const a = vi.fn(), k = vi.fn(), space = vi.fn();
    const { getByLabelText } = render(<Harness map={{ a, "mod+k": k, space }} />);
    fireEvent.keyDown(document.body, { key: "a" });
    expect(a).toHaveBeenCalledTimes(1);
    fireEvent.keyDown(getByLabelText("field"), { key: "a" });
    expect(a).toHaveBeenCalledTimes(1);
    fireEvent.keyDown(getByLabelText("field"), { key: "k", metaKey: true });
    fireEvent.keyDown(document.body, { key: "k", ctrlKey: true });
    expect(k).toHaveBeenCalledTimes(2);
    fireEvent.keyDown(document.body, { key: "a", ctrlKey: true });
    expect(a).toHaveBeenCalledTimes(1);
    fireEvent.keyDown(document.body, { key: " " });
    expect(space).toHaveBeenCalledTimes(1);
  });
});
