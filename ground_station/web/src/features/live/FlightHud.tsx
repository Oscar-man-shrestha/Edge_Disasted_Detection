import { useEffect, useRef, useState } from "react";
import { fmtNum, isNum } from "../../lib/format";
import { useLive } from "../../store/live";
import { cn } from "../../ui/cn";
import { Panel, PanelHeader } from "../../ui/Panel";
import { Sparkline } from "./Sparkline";

export function tempLevel(c: unknown): "ok" | "warm" | "hot" {
  return !isNum(c) ? "ok" : c >= 80 ? "hot" : c >= 70 ? "warm" : "ok";
}

function Compass({ deg }: { deg: number | null | undefined }) {
  const d = isNum(deg) ? deg : null;
  return (
    <svg viewBox="0 0 80 80" className="h-20 w-20 shrink-0" role="img" aria-label={d == null ? "Heading unknown" : `Heading ${Math.round(d)} degrees`}>
      <circle cx="40" cy="40" r="36" fill="var(--gs-surface-2)" stroke="var(--gs-line)" strokeWidth="2" />
      {Array.from({ length: 12 }, (_, i) => (
        <line key={i} x1="40" y1="6" x2="40" y2={i % 3 === 0 ? 13 : 10} stroke="var(--gs-muted)" strokeWidth={i % 3 === 0 ? 2 : 1} transform={`rotate(${i * 30} 40 40)`} />
      ))}
      <text x="40" y="22" textAnchor="middle" fontSize="9" fontWeight="700" fill="var(--gs-critical)">N</text>
      {d != null && (
        <g transform={`rotate(${d} 40 40)`} style={{ transition: "transform 0.4s ease" }}>
          <path d="M40 18 L47 46 L40 41 L33 46 Z" fill="var(--gs-text)" />
        </g>
      )}
      <text x="40" y="62" textAnchor="middle" fontSize="10" fontFamily="var(--font-mono)" fill="var(--gs-text-2)">
        {d == null ? "—" : `${Math.round(d)}°`}
      </text>
    </svg>
  );
}

function Gauge({ value, max, label, unit }: { value: number | null; max: number; label: string; unit: string }) {
  const f = value == null ? 0 : Math.max(0, Math.min(1, value / max));
  const r = 26, c = Math.PI * r;  // half circle
  return (
    <div className="flex flex-col items-center">
      <svg viewBox="0 0 64 38" className="h-12 w-20" role="img" aria-label={`${label} ${value == null ? "unknown" : value.toFixed(1) + " " + unit}`}>
        <path d="M6 34 A26 26 0 0 1 58 34" fill="none" stroke="var(--gs-surface-3)" strokeWidth="6" strokeLinecap="round" />
        <path d="M6 34 A26 26 0 0 1 58 34" fill="none" stroke="var(--gs-accent)" strokeWidth="6" strokeLinecap="round"
          strokeDasharray={`${c * f} ${c}`} style={{ transition: "stroke-dasharray 0.4s ease" }} />
      </svg>
      <span className="-mt-3 tabular font-mono text-sm font-semibold">{value == null ? "—" : value.toFixed(1)}<small className="text-text-2"> {unit}</small></span>
      <span className="text-[10px] uppercase tracking-wide text-muted">{label}</span>
    </div>
  );
}

function Stat({ k, v, unit, testId, level }: { k: string; v: string; unit?: string; testId?: string; level?: "ok" | "warm" | "hot" }) {
  return (
    <div className={cn("min-w-0 rounded-lg border bg-surface-2 px-2.5 py-1.5",
      level === "hot" ? "border-critical" : level === "warm" ? "border-warn" : "border-line")}>
      <div className="text-[10px] uppercase tracking-wide text-muted">{k}</div>
      <div data-testid={testId} className="tabular truncate font-mono text-[15px] font-semibold">
        {v}{unit && v !== "—" ? <small className="text-xs font-medium text-text-2"> {unit}</small> : null}
        {level === "hot" && <span className="ml-1 text-[10px] font-bold text-critical">HOT</span>}
        {level === "warm" && <span className="ml-1 text-[10px] font-bold text-warn">WARM</span>}
      </div>
    </div>
  );
}

export function FlightHud() {
  const t = useLive((s) => s.telemetry);
  const g = t?.gps ?? null, p = t?.pipeline ?? null, s = t?.system ?? null, l = t?.link ?? null;
  const powerW = isNum(s?.power_mw) ? s!.power_mw! / 1000 : null;

  // 60 s history for the sparklines, sampled once per second from the latest telemetry
  const latest = useRef({ fps: null as number | null, pow: null as number | null });
  latest.current = { fps: isNum(p?.fps) ? p!.fps! : null, pow: powerW };
  const [hist, setHist] = useState<{ fps: (number | null)[]; pow: (number | null)[] }>({ fps: [], pow: [] });
  useEffect(() => {
    const id = setInterval(() => setHist((h) => ({
      fps: [...h.fps, latest.current.fps].slice(-60), pow: [...h.pow, latest.current.pow].slice(-60),
    })), 1000);
    return () => clearInterval(id);
  }, []);

  const state = p?.state ?? null;
  return (
    <Panel>
      <PanelHeader title="Flight" right={
        <span className="flex items-center gap-1.5 text-xs font-semibold">
          <span aria-hidden className={cn("h-2 w-2 rounded-full", state === "active" ? "bg-fire" : state === "scanning" ? "bg-good" : "bg-muted")} />
          {state ? state.toUpperCase() : "—"}
        </span>
      } />
      <div className="flex items-center gap-3 px-3">
        <Compass deg={g?.course_deg} />
        <div className="grid flex-1 grid-cols-2 gap-1.5">
          <Stat k="Speed" v={fmtNum(g?.speed_mps, 1)} unit="m/s" testId="hud-speed" />
          <Stat k="Altitude" v={fmtNum(g?.alt_m, 0)} unit="m" />
          <Stat k="Satellites" v={fmtNum(g?.sats)} />
          <Stat k="HDOP" v={fmtNum(g?.hdop, 1)} />
        </div>
      </div>
      <div className="mt-2 grid grid-cols-3 gap-1.5 px-3">
        <Stat k="Frame rate" v={fmtNum(p?.fps, 1)} unit="fps" />
        <Stat k="Stage 1" v={fmtNum(p?.stage1_ms, 1)} unit="ms" />
        <Stat k="YOLO" v={fmtNum(p?.stage2_ms, 0)} unit="ms" />
        <Stat k="YOLO runs" v={fmtNum(p?.stage2_runs)} />
        <Stat k="Skipped" v={fmtNum(p?.stage2_skipped)} />
        <Stat k="Waiting" v={fmtNum(l?.alerts_buffered)} unit="alerts" />
      </div>
      <div className="mt-2 flex items-center gap-2 px-3">
        <Gauge value={powerW} max={10} label="Power" unit="W" />
        <div className="grid flex-1 grid-cols-2 gap-1.5">
          <Stat k="CPU temp" v={fmtNum(s?.cpu_temp_c, 0)} unit="°C" level={tempLevel(s?.cpu_temp_c)} />
          <Stat k="GPU temp" v={fmtNum(s?.gpu_temp_c, 0)} unit="°C" level={tempLevel(s?.gpu_temp_c)} />
          <Stat k="CPU / GPU" v={`${fmtNum(s?.cpu_load_pct)} / ${fmtNum(s?.gpu_load_pct)}`} unit="%" />
          <Stat k="Memory" v={isNum(s?.ram_used_mb) ? (s!.ram_used_mb! / 1024).toFixed(1) : "—"}
            unit={isNum(s?.ram_total_mb) ? `/ ${(s!.ram_total_mb! / 1024).toFixed(1)} GB` : "GB"} />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3 px-3 pb-3 pt-2">
        <div><div className="flex justify-between text-[10px] uppercase tracking-wide text-muted"><span>Frame rate</span><b className="text-text">{fmtNum(p?.fps, 1)}</b></div>
          <Sparkline data={hist.fps} unit="fps" label="Frame rate" /></div>
        <div><div className="flex justify-between text-[10px] uppercase tracking-wide text-muted"><span>Power</span><b className="text-text">{powerW == null ? "—" : powerW.toFixed(1) + " W"}</b></div>
          <Sparkline data={hist.pow} unit="W" label="Board power" /></div>
      </div>
    </Panel>
  );
}
