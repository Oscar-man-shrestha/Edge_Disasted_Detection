import { Expand } from "lucide-react";
import { useEffect, useState } from "react";
import { previewUrl } from "../../lib/api";
import { useServerNow } from "../../hooks/useServerNow";
import { useLive } from "../../store/live";
import { DialogContent, DialogRoot, DialogTrigger } from "../../ui/Dialog";
import { Panel, PanelHeader } from "../../ui/Panel";

export const PREVIEW_STALE_S = 5;

export function CameraCard() {
  const preview = useLive((s) => s.preview);
  const now = useServerNow(500);
  const [src, setSrc] = useState<string | null>(null);
  useEffect(() => {
    if (!preview) return;
    const next = previewUrl(preview.t);
    const img = new Image();
    img.onload = () => setSrc(next);          // swap only once the new frame has loaded (no flicker)
    img.src = next;
    if (!src) setSrc(next);
  }, [preview?.t]); // eslint-disable-line react-hooks/exhaustive-deps
  const age = preview ? Math.max(0, now - preview.t) : null;
  const stale = age != null && age >= PREVIEW_STALE_S;
  const label = age == null ? "no image yet" : age < 1.5 ? "live" : `${Math.round(age)} s ago`;

  const frame = (big: boolean) => (
    <div className={big ? "relative bg-black" : "relative aspect-video overflow-hidden rounded-lg border border-line bg-black"}>
      {src ? <img src={src} alt="Latest camera preview from the drone" className={big ? "max-h-[78vh] w-full object-contain" : "h-full w-full object-cover"} />
        : <div className="grid h-full place-items-center p-4 text-center text-xs text-muted">Waiting for the first camera preview…</div>}
      {preview?.stage2 && !stale && (
        <span className="absolute left-2 top-2 rounded-md bg-fire px-2 py-0.5 text-[10px] font-extrabold tracking-wider text-white shadow">YOLO ACTIVE</span>
      )}
      {stale && <div className="absolute inset-0 grid place-items-center bg-black/55 text-sm font-bold tracking-widest text-warn">STALE</div>}
    </div>
  );

  return (
    <Panel>
      <PanelHeader title="Camera" right={
        <span className="flex items-center gap-2">
          <span className="text-[11px] text-muted">{label}</span>
          <DialogRoot>
            <DialogTrigger asChild>
              <button type="button" aria-label="Full screen camera" className="rounded p-1 text-muted hover:bg-surface-2 hover:text-text"><Expand size={14} /></button>
            </DialogTrigger>
            <DialogContent title="Camera" className="!w-[min(1100px,calc(100vw-24px))]">{frame(true)}</DialogContent>
          </DialogRoot>
        </span>
      } />
      <div className="px-3 pb-3">{frame(false)}</div>
    </Panel>
  );
}
