import { useServerNow } from "../../hooks/useServerNow";
import { linkState, useLive } from "../../store/live";
import { cn } from "../../ui/cn";

export function LinkPill() {
  const now = useServerNow(500);
  const telemetryAt = useLive((s) => s.telemetryAt);
  const drone = useLive((s) => s.telemetry?.drone_id);
  const connection = useLive((s) => s.connection);
  const link = linkState({ telemetryAt }, now);
  const text = connection === "reconnecting" ? "Reconnecting…"
    : link.state === "live" ? `LIVE${drone ? ` · ${drone}` : ""}`
    : link.state === "lost" ? `LINK LOST · ${Math.round(link.age_s ?? 0)} s` : "WAITING FOR DRONE";
  const tone = connection === "reconnecting" ? "warn" : link.state;
  // Screen readers hear state changes only, never the ticking "N s" age.
  const spoken = connection === "reconnecting" ? "Reconnecting to the ground station"
    : link.state === "live" ? "Drone link live" : link.state === "lost" ? "Drone link lost" : "Waiting for drone";
  return (
    <>
    <span data-testid="link-announcer" aria-live="polite" className="sr-only">{spoken}</span>
    <div data-testid="link-pill"
      className={cn("inline-flex h-8 items-center gap-2 rounded-full border px-3 text-xs font-bold tracking-wide whitespace-nowrap",
        tone === "live" && "border-good/60 bg-good/10 text-text",
        tone === "lost" && "animate-pulse border-critical bg-critical/20 text-text",
        tone === "never" && "border-line bg-surface-2 text-text-2",
        tone === "warn" && "border-warn/60 bg-warn/10 text-text")}>
      <span aria-hidden className={cn("h-2 w-2 rounded-full",
        tone === "live" && "bg-good [animation:gs-ping_1.6s_infinite]", tone === "lost" && "bg-critical",
        tone === "never" && "bg-muted", tone === "warn" && "bg-warn")} />
      {text}
    </div>
    </>
  );
}

export function GpsChip() {
  const g = useLive((s) => s.telemetry?.gps);
  let text = "GPS —", ok: boolean | null = null;
  if (g) {
    if (g.fix === true) {
      ok = true;
      text = [g.mode === "sim" ? "SIM GPS" : "FIX", g.sats != null ? `${g.sats} sats` : null,
        g.hdop != null ? `HDOP ${g.hdop.toFixed(1)}` : null].filter(Boolean).join(" · ");
    } else { ok = false; text = `NO FIX${g.sats != null ? ` · ${g.sats} sats` : ""}`; }
  }
  return (
    <div className={cn("hidden h-8 items-center rounded-full border border-line bg-surface-2 px-3 text-xs font-semibold whitespace-nowrap sm:inline-flex",
      ok === true && "text-text", ok === false && "text-serious", ok === null && "text-muted")}>{text}</div>
  );
}
