import { afterEach, describe, expect, it, vi } from "vitest";
import { connect, STREAM_EVENTS } from "../../src/lib/sse";

class FakeES {
  static last: FakeES;
  listeners: Record<string, ((e: MessageEvent) => void)[]> = {};
  closed = false;
  constructor(public url: string) { FakeES.last = this; }
  addEventListener(name: string, fn: (e: MessageEvent) => void) { (this.listeners[name] ??= []).push(fn); }
  emit(name: string, data?: unknown) {
    (this.listeners[name] ?? []).forEach((fn) => fn(new MessageEvent(name, { data: data === undefined ? undefined : JSON.stringify(data) })));
  }
  close() { this.closed = true; }
}

describe("sse", () => {
  afterEach(() => vi.unstubAllGlobals());
  it("wires open, error and named events", () => {
    vi.stubGlobal("EventSource", FakeES);
    const onEvent = vi.fn(), onOpen = vi.fn(), onState = vi.fn();
    const stop = connect({ onEvent, onOpen, onState });
    expect(FakeES.last.url).toBe("/api/stream");
    expect(STREAM_EVENTS).toEqual(["hello", "telemetry", "preview", "alert", "alert_update", "link", "mission"]);
    FakeES.last.emit("open");
    expect(onOpen).toHaveBeenCalledTimes(1);
    expect(onState).toHaveBeenLastCalledWith("open");
    FakeES.last.emit("alert", { alert: { id: 1 } });
    expect(onEvent).toHaveBeenCalledWith("alert", { alert: { id: 1 } });
    FakeES.last.emit("error");
    expect(onState).toHaveBeenLastCalledWith("reconnecting");
    stop();
    expect(FakeES.last.closed).toBe(true);
  });
});
