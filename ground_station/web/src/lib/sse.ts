export const STREAM_EVENTS = ["hello", "telemetry", "preview", "alert", "alert_update", "link", "mission"] as const;
export type StreamEvent = (typeof STREAM_EVENTS)[number];
export type ConnectionState = "connecting" | "open" | "reconnecting";

export interface StreamHandlers {
  onEvent(name: StreamEvent, data: unknown): void;
  /** Called on every (re)connect: the caller resyncs from /api/state. */
  onOpen(): void;
  onState(state: ConnectionState): void;
}

/** Live station events over SSE. EventSource reconnects by itself; returns a stop function. */
export function connect(h: StreamHandlers, url = "/api/stream"): () => void {
  const es = new EventSource(url);
  h.onState("connecting");
  es.addEventListener("open", () => { h.onState("open"); h.onOpen(); });
  es.addEventListener("error", () => h.onState("reconnecting"));
  for (const name of STREAM_EVENTS) {
    es.addEventListener(name, (e: Event) => {
      const raw = (e as MessageEvent).data;
      if (typeof raw !== "string") return;
      try { h.onEvent(name, JSON.parse(raw)); } catch { /* malformed event: ignore */ }
    });
  }
  return () => es.close();
}
