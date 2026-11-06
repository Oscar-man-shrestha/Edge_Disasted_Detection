import { ArrowLeft, Check, CheckCheck, Copy, Film, Image as ImageIcon, LocateFixed, RotateCcw, ZoomIn } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { snapUrl } from "../../lib/api";
import { fmtClock, fmtCoord } from "../../lib/format";
import type { Alert } from "../../lib/types";
import { useMapCommand } from "../../store/ui";
import { StatusBadge, TypeBadge } from "../../ui/Badge";
import { Button } from "../../ui/Button";
import { cn } from "../../ui/cn";
import { saveAlertNote, setAlertStatus } from "./actions";
import { ClipPlayer } from "./ClipPlayer";

export function AlertDetail({ alert: a, onBack }: { alert: Alert; onBack(): void }) {
  const [zoom, setZoom] = useState(false);
  const [note, setNote] = useState(a.note ?? "");
  const [busy, setBusy] = useState(false);
  const hasClip = (a.clip_frames ?? 0) > 0;
  const [view, setView] = useState<"photo" | "clip">("photo");
  useEffect(() => setNote(a.note ?? ""), [a.id, a.note]);
  useEffect(() => setView("photo"), [a.id]);
  const located = a.lat != null && a.lon != null;
  const act = async (f: () => Promise<boolean>) => { setBusy(true); await f(); setBusy(false); };

  return (
    <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-4">
      <button type="button" onClick={onBack} className="mb-2 flex items-center gap-1 text-xs font-semibold text-text-2 hover:text-text">
        <ArrowLeft size={14} /> All alerts
      </button>
      <div className="flex items-center gap-2">
        <TypeBadge type={a.type} />
        <b className="tabular font-mono text-lg">{Math.round(a.conf * 100)}%</b>
        <StatusBadge status={a.status} />
        <span className="ml-auto text-xs text-muted">#{a.id}</span>
      </div>

      {hasClip && (
        <div className="mt-3 inline-flex rounded-lg border border-line p-0.5 text-xs font-semibold" role="group" aria-label="Photo or clip">
          {(["photo", "clip"] as const).map((v) => (
            <button key={v} type="button" aria-pressed={view === v} onClick={() => setView(v)}
              className={cn("flex items-center gap-1 rounded-md px-2.5 py-1", view === v ? "bg-surface-3 text-text" : "text-text-2 hover:text-text")}>
              {v === "photo" ? <ImageIcon size={13} /> : <Film size={13} />} {v === "photo" ? "Photo" : `Clip (${Math.round((a.clip_frames ?? 0) / (a.clip_fps || 2))} s)`}
            </button>
          ))}
        </div>
      )}

      {hasClip && view === "clip" ? <ClipPlayer alertId={a.id} frames={a.clip_frames!} fps={a.clip_fps ?? 2} /> : a.snapshot ? (
        <button type="button" onClick={() => setZoom((z) => !z)} aria-label={zoom ? "Zoom out snapshot" : "Zoom in snapshot"}
          className="relative mt-3 block w-full overflow-hidden rounded-lg border border-line bg-black">
          <img src={snapUrl(a.snapshot)} alt={`${a.type} alert ${a.id} snapshot`}
            className={cn("w-full transition-transform duration-200", zoom ? "scale-200 cursor-zoom-out" : "cursor-zoom-in")} />
          {!zoom && <ZoomIn size={16} className="absolute bottom-2 right-2 text-white drop-shadow" aria-hidden />}
        </button>
      ) : <div className="mt-3 grid h-28 place-items-center rounded-lg border border-line text-sm text-muted">No snapshot</div>}

      <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 text-sm">
        <dt className="text-muted">Position</dt>
        <dd className={cn("tabular font-mono", !located && "font-sans font-semibold text-serious")}>{fmtCoord(a.lat, a.lon)}</dd>
        <dt className="text-muted">Received</dt><dd className="tabular font-mono">{fmtClock(a.received_at)}</dd>
        <dt className="text-muted">Drone time</dt><dd className="tabular font-mono">{a.wall_time ?? "—"}</dd>
        {a.acked_at && (<><dt className="text-muted">Acknowledged</dt><dd className="tabular font-mono">{a.acked_at}</dd></>)}
        {a.resolved_at && (<><dt className="text-muted">Resolved</dt><dd className="tabular font-mono">{a.resolved_at}</dd></>)}
      </dl>

      {located && (
        <div className="mt-3 flex gap-2">
          <Button size="sm" onClick={() => useMapCommand.getState().send({ type: "flyTo", lat: a.lat!, lon: a.lon! })}>
            <LocateFixed size={14} /> Fly to
          </Button>
          <Button size="sm" variant="ghost" onClick={async () => {
            try { await navigator.clipboard.writeText(fmtCoord(a.lat, a.lon)); toast("Coordinates copied"); }
            catch { toast(fmtCoord(a.lat, a.lon)); }
          }}><Copy size={14} /> Copy</Button>
        </div>
      )}

      <div className="mt-4 flex flex-wrap gap-2">
        {a.status === "new" && <Button variant="primary" disabled={busy} onClick={() => act(() => setAlertStatus(a, "acknowledged"))}><Check size={14} /> Acknowledge</Button>}
        {a.status !== "resolved" && <Button variant="success" disabled={busy} onClick={() => act(() => setAlertStatus(a, "resolved"))}><CheckCheck size={14} /> Resolve</Button>}
        {a.status === "resolved" && <Button disabled={busy} onClick={() => act(() => setAlertStatus(a, "acknowledged"))}><RotateCcw size={14} /> Reopen</Button>}
      </div>

      <form className="mt-4" onSubmit={(e) => { e.preventDefault(); act(() => saveAlertNote(a, note)); }}>
        <label htmlFor={`note-${a.id}`} className="text-xs font-semibold uppercase tracking-wide text-muted">Note</label>
        <textarea id={`note-${a.id}`} value={note} onChange={(e) => setNote(e.target.value)} rows={3} maxLength={500}
          placeholder="e.g. Rescue team 2 dispatched"
          className="mt-1 w-full resize-y rounded-lg border border-line bg-surface-2 px-3 py-2 text-sm outline-none focus:border-accent" />
        <Button type="submit" size="sm" disabled={busy || note === (a.note ?? "")}>Save note</Button>
      </form>
    </div>
  );
}
