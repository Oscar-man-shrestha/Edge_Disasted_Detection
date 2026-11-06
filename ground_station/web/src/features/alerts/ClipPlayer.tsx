import { Pause, Play } from "lucide-react";
import { useEffect, useState } from "react";
import { clipFrameUrl } from "../../lib/api";

/** Plays an alert clip: JPEG frames from the drone, a few seconds around the detection. */
export function ClipPlayer({ alertId, frames, fps }: { alertId: number; frames: number; fps: number }) {
  const [i, setI] = useState(0);
  const [playing, setPlaying] = useState(true);
  const rate = Math.min(10, Math.max(0.5, fps || 2));

  useEffect(() => {                                   // warm the cache so playback is smooth
    for (let k = 0; k < frames; k++) new Image().src = clipFrameUrl(alertId, k);
  }, [alertId, frames]);

  useEffect(() => {
    if (!playing || frames < 2) return;
    const h = window.setInterval(() => setI((k) => (k + 1) % frames), 1000 / rate);
    return () => window.clearInterval(h);
  }, [playing, frames, rate]);

  return (
    <div className="relative mt-3 overflow-hidden rounded-lg border border-line bg-black">
      <img src={clipFrameUrl(alertId, i)} alt={`alert ${alertId} clip frame ${i + 1} of ${frames}`} className="w-full" />
      <div className="absolute inset-x-0 bottom-0 flex items-center gap-2 bg-black/55 px-2 py-1 text-xs text-white">
        <button type="button" onClick={() => setPlaying((p) => !p)} aria-label={playing ? "Pause clip" : "Play clip"}
          className="grid h-6 w-6 place-items-center rounded hover:bg-white/20">
          {playing ? <Pause size={14} /> : <Play size={14} />}
        </button>
        <input type="range" min={0} max={frames - 1} value={i} aria-label="Clip position"
          onChange={(e) => { setPlaying(false); setI(Number(e.target.value)); }} className="flex-1 accent-white" />
        <span className="tabular font-mono">{i + 1}/{frames}</span>
      </div>
    </div>
  );
}
