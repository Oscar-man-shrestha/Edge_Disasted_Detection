import { useEffect, useRef, useState } from "react";

/** 60-sample canvas sparkline with a hover readout. Single series: the caption names it. */
export function Sparkline({ data, unit, digits = 1, label }: { data: (number | null)[]; unit: string; digits?: number; label: string }) {
  const ref = useRef<HTMLCanvasElement>(null);
  const [hover, setHover] = useState<number | null>(null);
  const N = 60;
  useEffect(() => {
    const cv = ref.current;
    if (!cv) return;
    const ctx = cv.getContext?.("2d");
    if (!ctx) return;
    const dpr = window.devicePixelRatio || 1, w = cv.clientWidth || 260, h = cv.clientHeight || 40;
    cv.width = w * dpr; cv.height = h * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    const css = getComputedStyle(document.documentElement);
    ctx.strokeStyle = css.getPropertyValue("--gs-line") || "#2a3140";
    ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(0, h - 0.5); ctx.lineTo(w, h - 0.5); ctx.stroke();
    const vals = data.filter((v): v is number => v != null);
    if (vals.length < 2) return;
    const max = Math.max(...vals) * 1.15 || 1;
    const x = (i: number) => ((i + N - data.length) / (N - 1)) * (w - 4) + 2;
    const y = (v: number) => h - 3 - (v / max) * (h - 8);
    const accent = css.getPropertyValue("--gs-accent") || "#3987e5";
    ctx.strokeStyle = accent; ctx.lineWidth = 2; ctx.lineJoin = "round"; ctx.lineCap = "round";
    ctx.beginPath();
    let pen = false;
    data.forEach((v, i) => { if (v == null) { pen = false; return; } if (!pen) { ctx.moveTo(x(i), y(v)); pen = true; } else ctx.lineTo(x(i), y(v)); });
    ctx.stroke();
    if (hover != null && data[hover] != null) {
      ctx.strokeStyle = css.getPropertyValue("--gs-muted") || "#7a8293"; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(x(hover), 0); ctx.lineTo(x(hover), h); ctx.stroke();
      ctx.fillStyle = accent; ctx.beginPath(); ctx.arc(x(hover), y(data[hover]!), 4, 0, Math.PI * 2); ctx.fill();
    }
  }, [data, hover]);
  const ago = hover != null ? data.length - 1 - hover : null;
  return (
    <div className="relative">
      <canvas ref={ref} aria-label={`${label}, last 60 seconds`} role="img" className="h-10 w-full cursor-crosshair"
        onMouseLeave={() => setHover(null)}
        onMouseMove={(e) => {
          const r = e.currentTarget.getBoundingClientRect();
          const slot = Math.round(((e.clientX - r.left - 2) / (r.width - 4)) * (N - 1));
          setHover(Math.min(data.length - 1, Math.max(0, slot - (N - data.length))));
        }} />
      {hover != null && (
        <span className="pointer-events-none absolute -top-6 right-0 rounded border border-line bg-surface-3 px-1.5 py-0.5 text-[11px]">
          {data[hover] == null ? "no data" : `${data[hover]!.toFixed(digits)} ${unit}`} · {ago ? `${ago} s ago` : "now"}
        </span>
      )}
    </div>
  );
}
