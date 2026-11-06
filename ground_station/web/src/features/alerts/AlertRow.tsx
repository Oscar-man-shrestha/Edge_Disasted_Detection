import { Film } from "lucide-react";
import { memo } from "react";
import { snapUrl } from "../../lib/api";
import { fmtClock, fmtCoord } from "../../lib/format";
import type { Alert } from "../../lib/types";
import { StatusBadge, TYPE_BORDER, TypeBadge } from "../../ui/Badge";
import { cn } from "../../ui/cn";

export const AlertRow = memo(function AlertRow({ alert: a, selected, onSelect }: {
  alert: Alert; selected: boolean; onSelect(id: number): void;
}) {
  return (
    <li>
      <button type="button" onClick={() => onSelect(a.id)} aria-current={selected || undefined}
        className={cn("grid w-full grid-cols-[72px_1fr] gap-2.5 rounded-xl border border-l-4 bg-surface-2 p-2 text-left transition-colors hover:bg-surface-3",
          TYPE_BORDER[a.type], selected ? "border-y-accent border-r-accent ring-1 ring-accent" : "border-y-line border-r-line",
          a.status === "resolved" && "opacity-60")}>
        {a.snapshot
          ? <img src={snapUrl(a.snapshot)} alt="" loading="lazy" className="h-[52px] w-[72px] rounded-md border border-line object-cover" />
          : <span className="grid h-[52px] w-[72px] place-items-center rounded-md border border-line text-[10px] text-muted">no image</span>}
        <span className="min-w-0">
          <span className="flex flex-wrap items-center gap-1.5">
            <TypeBadge type={a.type} />
            <b className="tabular font-mono text-sm">{Math.round(a.conf * 100)}%</b>
            <StatusBadge status={a.status} />
            {(a.clip_frames ?? 0) > 0 && <Film size={13} className="text-text-2" aria-label="has clip" />}
            <span className="ml-auto text-[11px] text-muted">#{a.id}</span>
          </span>
          <span className="mt-1 block truncate text-xs text-text-2">
            <span className="tabular font-mono">{fmtClock(a.received_at)}</span> ·{" "}
            <span className={cn(a.lat == null && "font-semibold text-serious")}>{fmtCoord(a.lat, a.lon)}</span>
          </span>
          {a.note && <span className="mt-1 block truncate text-xs text-text">“{a.note}”</span>}
        </span>
      </button>
    </li>
  );
});
