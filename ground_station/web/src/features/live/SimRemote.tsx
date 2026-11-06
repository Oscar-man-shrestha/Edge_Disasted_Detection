import { ArrowDown, ArrowLeft, ArrowRight, ArrowUp, Gamepad2, Square } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { simControl } from "../../lib/api";
import { isNum } from "../../lib/format";
import { useLive } from "../../store/live";
import { cn } from "../../ui/cn";

const TURN = 15;          // degrees per press
const STEP = 1;           // m/s per press
const MAX = 15;

const wrap = (h: number) => ((Math.round(h) % 360) + 360) % 360;

/** Temporary remote for the SIMULATED drone (EDGE_GPS=sim): auto patrol or manual steering.
 *  Commands go to the station and reach the drone in its next telemetry reply (~1 s).
 *  Only shown while the drone reports a simulated GPS; a real GPS ignores it. */
export function SimRemote() {
  const gps = useLive((s) => s.telemetry?.gps);
  const control = gps?.control ?? "auto";
  const [cmd, setCmd] = useState<{ heading: number; speed: number } | null>(null);
  const cmdRef = useRef(cmd);
  cmdRef.current = cmd;
  const manual = cmd != null;

  const send = async (next: { heading: number; speed: number } | null) => {
    cmdRef.current = next;            // fast key repeats build on this one, not on the last render
    setCmd(next);
    try { await simControl(next ? { mode: "manual", ...next } : { mode: "auto" }); }
    catch (e) { toast.error(`Remote: ${(e as Error).message}`); }
  };
  const takeOver = () => send({ heading: wrap(isNum(gps?.course_deg) ? gps!.course_deg! : 0),
    speed: isNum(gps?.speed_mps) && gps!.speed_mps! > 0 ? Math.round(gps!.speed_mps!) : 5 });
  const nudge = (dh: number, ds: number) => {
    const c = cmdRef.current;
    if (c) send({ heading: wrap(c.heading + dh), speed: Math.min(MAX, Math.max(0, c.speed + ds)) });
  };
  const hover = () => { const c = cmdRef.current; if (c) send({ ...c, speed: 0 }); };

  // keyboard: arrows steer, space hovers (manual only; never while typing or on the map)
  useEffect(() => {
    if (!manual) return;
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as Element | null;
      if (e.metaKey || e.ctrlKey || e.altKey || t?.closest?.("input, textarea, select, [contenteditable], .maplibregl-map")) return;
      const k = e.key;
      if (k === "ArrowLeft") nudge(-TURN, 0); else if (k === "ArrowRight") nudge(TURN, 0);
      else if (k === "ArrowUp") nudge(0, STEP); else if (k === "ArrowDown") nudge(0, -STEP);
      else if (k === " ") hover(); else return;
      e.preventDefault();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [manual]); // eslint-disable-line react-hooks/exhaustive-deps

  if (gps?.mode !== "sim") return null;
  const pad = "grid h-10 w-10 place-items-center rounded-lg border border-line bg-surface-2 hover:bg-surface-3 active:scale-95 disabled:opacity-40";
  const status = control === "manual" ? "Manual" : control === "return" ? "Returning to route" : "Auto patrol";

  return (
    <section aria-label="Simulator remote" className="rounded-2xl border border-line bg-surface p-3 shadow-panel">
      <div className="flex items-center gap-2">
        <Gamepad2 size={15} className="text-accent" aria-hidden />
        <h2 className="text-xs font-semibold uppercase tracking-wide text-muted">Simulator remote</h2>
        <span className={cn("ml-auto rounded-full px-2 py-0.5 text-[11px] font-semibold",
          control === "manual" ? "bg-warn/20 text-warn" : "bg-good/15 text-good")} aria-live="polite">{status}</span>
      </div>

      <div className="mt-2 inline-flex w-full rounded-lg border border-line p-0.5 text-xs font-semibold" role="group" aria-label="Who flies the drone">
        <button type="button" aria-pressed={!manual} onClick={() => send(null)}
          className={cn("flex-1 rounded-md py-1.5", !manual ? "bg-surface-3 text-text" : "text-text-2 hover:text-text")}>Auto patrol</button>
        <button type="button" aria-pressed={manual} onClick={() => (manual ? undefined : takeOver())}
          className={cn("flex-1 rounded-md py-1.5", manual ? "bg-surface-3 text-text" : "text-text-2 hover:text-text")}>Manual</button>
      </div>

      {manual && (
        <div className="mt-3 flex items-center gap-4">
          <div className="grid grid-cols-3 gap-1" aria-label="Steering">
            <span />
            <button type="button" className={pad} aria-label="Faster" onClick={() => nudge(0, STEP)} disabled={cmd!.speed >= MAX}><ArrowUp size={16} /></button>
            <span />
            <button type="button" className={pad} aria-label="Turn left" onClick={() => nudge(-TURN, 0)}><ArrowLeft size={16} /></button>
            <button type="button" className={pad} aria-label="Hover" onClick={hover}><Square size={14} /></button>
            <button type="button" className={pad} aria-label="Turn right" onClick={() => nudge(TURN, 0)}><ArrowRight size={16} /></button>
            <span />
            <button type="button" className={pad} aria-label="Slower" onClick={() => nudge(0, -STEP)} disabled={cmd!.speed <= 0}><ArrowDown size={16} /></button>
            <span />
          </div>
          <dl className="grid grid-cols-[auto_1fr] gap-x-2 gap-y-1 text-sm">
            <dt className="text-muted">Heading</dt><dd className="tabular font-mono">{String(cmd!.heading).padStart(3, "0")}°</dd>
            <dt className="text-muted">Speed</dt><dd className="tabular font-mono">{cmd!.speed.toFixed(0)} m/s</dd>
            <dt className="text-muted">Keys</dt><dd className="text-xs text-text-2">← → turn · ↑ ↓ speed · space hover</dd>
          </dl>
        </div>
      )}
      <p className="mt-2 text-[11px] text-muted">Simulated GPS only. Commands reach the drone within about 1 s.</p>
    </section>
  );
}
