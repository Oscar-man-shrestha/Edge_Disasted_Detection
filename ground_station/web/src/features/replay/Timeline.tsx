import { fmtDuration } from "../../lib/format";
import type { Timeline as TL } from "../../lib/types";
import { cn } from "../../ui/cn";
import { alertTime, segments, type Bounds } from "./replay";

const STATE_BG: Record<string, string> = { active: "bg-fire", scanning: "bg-good/70", idle: "bg-surface-3" };
const TICK_BG = { person: "bg-person", fire: "bg-fire", smoke: "bg-smoke" } as const;

export function Timeline({ tl, b, t, onSeek }: { tl: TL; b: Bounds; t: number; onSeek(t: number): void }) {
  const span = Math.max(1, b.end - b.start);
  const pct = (x: number) => `${((x - b.start) / span) * 100}%`;
  return (
    <div className="w-full">
      <div className="relative h-5">
        {tl.alerts.map((a) => {
          const at = alertTime(a, tl);
          return (
            <button key={a.id} type="button" title={`${a.type} #${a.id} at ${fmtDuration(at - b.start)}`}
              aria-label={`${a.type} alert #${a.id} at ${fmtDuration(at - b.start)}`}
              onClick={() => onSeek(at)}
              className={cn("absolute top-0 h-4 w-1.5 -translate-x-1/2 rounded-sm ring-1 ring-surface hover:h-5", TICK_BG[a.type],
                at > t && "opacity-40")}
              style={{ left: pct(at) }} />
          );
        })}
      </div>
      {/* whole-second steps, but the right end is the real end: rounding could otherwise stop
          short of it and hide the newest alert (e.g. at 15.3 s with max 15) */}
      <input type="range" aria-label="Replay time" min={0} max={Math.ceil(span)} step={1}
        value={t >= b.end ? Math.ceil(span) : Math.round(t - b.start)}
        onChange={(e) => { const v = Number(e.target.value); onSeek(v >= Math.ceil(span) ? b.end : b.start + v); }}
        aria-valuetext={`${fmtDuration(t - b.start)} of ${fmtDuration(span)}`}
        className="h-2 w-full cursor-pointer accent-[var(--gs-accent)]" />
      <div aria-hidden className="relative mt-1 h-1.5 w-full overflow-hidden rounded-full bg-surface-3">
        {segments(tl).map((s, i) => (
          <span key={i} className={cn("absolute inset-y-0", STATE_BG[s.state] ?? "bg-surface-3")}
            style={{ left: pct(s.start), width: `${((s.end - s.start) / span) * 100}%` }} />
        ))}
      </div>
      <div className="mt-1 flex justify-between text-[11px] text-muted">
        <span className="tabular font-mono">{fmtDuration(t - b.start)}</span>
        <span className="flex gap-3"><Legend c="bg-good/70" l="scanning" /><Legend c="bg-fire" l="YOLO active" /><Legend c="bg-surface-3" l="idle" /></span>
        <span className="tabular font-mono">{fmtDuration(span)}</span>
      </div>
    </div>
  );
}

const Legend = ({ c, l }: { c: string; l: string }) => (
  <span className="flex items-center gap-1"><i aria-hidden className={cn("h-2 w-3 rounded-sm", c)} />{l}</span>
);
