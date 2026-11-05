import { fmtClock, fmtNum } from "../../lib/format";
import type { TelemetrySample } from "../../lib/types";

const MAX_ROWS = 2000;

export function TelemetryTable({ rows }: { rows: TelemetrySample[] }) {
  const shown = rows.slice(-MAX_ROWS);
  return (
    <div className="overflow-auto rounded-xl border border-line bg-surface">
      {rows.length > MAX_ROWS && <p className="px-3 py-2 text-xs text-muted">Showing the last {MAX_ROWS} of {rows.length} samples. Use CSV export for all data.</p>}
      <table className="w-full text-left text-sm">
        <caption className="sr-only">Telemetry samples</caption>
        <thead className="sticky top-0 bg-surface-2 text-[11px] uppercase tracking-wide text-muted">
          <tr>{["Time", "State", "FPS", "Power W", "CPU °C", "GPU °C", "Speed m/s", "Sats", "YOLO runs", "Skipped"].map((h) => <th key={h} className="px-3 py-2 font-semibold">{h}</th>)}</tr>
        </thead>
        <tbody className="tabular font-mono">
          {shown.map((s) => (
            <tr key={s.t} className="border-t border-line">
              <td className="px-3 py-1.5">{fmtClock(s.t)}</td><td className="px-3 py-1.5 font-sans">{s.state ?? "—"}</td>
              <td className="px-3 py-1.5">{fmtNum(s.fps, 1)}</td><td className="px-3 py-1.5">{s.power_mw == null ? "—" : (s.power_mw / 1000).toFixed(1)}</td>
              <td className="px-3 py-1.5">{fmtNum(s.cpu_temp_c)}</td><td className="px-3 py-1.5">{fmtNum(s.gpu_temp_c)}</td>
              <td className="px-3 py-1.5">{fmtNum(s.speed_mps, 1)}</td><td className="px-3 py-1.5">{fmtNum(s.sats)}</td>
              <td className="px-3 py-1.5">{fmtNum(s.stage2_runs)}</td><td className="px-3 py-1.5">{fmtNum(s.stage2_skipped)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
