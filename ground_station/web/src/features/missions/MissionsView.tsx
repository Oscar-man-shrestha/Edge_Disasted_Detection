import { useQuery } from "@tanstack/react-query";
import { ChartColumn, FileText, History, Plus } from "lucide-react";
import { exportUrl, getMissions, reportUrl } from "../../lib/api";
import { fmtDuration } from "../../lib/format";
import { ALERT_TYPES } from "../../lib/types";
import { useServerNow } from "../../hooks/useServerNow";
import { useOverlays } from "../../store/ui";
import { TYPE_TEXT } from "../../ui/Badge";
import { Button } from "../../ui/Button";
import { cn } from "../../ui/cn";

export default function MissionsView() {
  const q = useQuery({ queryKey: ["missions"], queryFn: getMissions, refetchInterval: 30_000 });
  const now = useServerNow(5000);
  const missions = [...(q.data ?? [])].reverse();
  const link = "inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-semibold text-text-2 hover:bg-surface-3 hover:text-text";
  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-[1200px] p-4">
        <div className="mb-4 flex items-center gap-3">
          <h1 className="text-xl font-semibold">Missions</h1>
          <span className="text-sm text-muted">{missions.length} total</span>
          <Button variant="primary" className="ml-auto" onClick={() => useOverlays.getState().set({ newMission: true })}><Plus size={14} /> New mission</Button>
        </div>
        <div className="overflow-x-auto rounded-xl border border-line bg-surface shadow-panel">
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead className="bg-surface-2 text-[11px] uppercase tracking-wide text-muted">
              <tr>{["Mission", "Started", "Duration", "Alerts", "Distance", ""].map((h) => <th key={h} className="px-3 py-2 font-semibold">{h}</th>)}</tr>
            </thead>
            <tbody>
              {missions.map((m) => (
                <tr key={m.id} className="border-t border-line align-middle">
                  <td className="px-3 py-2 font-semibold">{m.name}{m.ended_ts == null && <span className="ml-2 rounded-full bg-good/15 px-2 py-0.5 text-[10px] font-bold text-good">CURRENT</span>}</td>
                  <td className="tabular px-3 py-2 font-mono text-text-2">{m.started_at}</td>
                  <td className="tabular px-3 py-2 font-mono">{fmtDuration((m.ended_ts ?? now) - m.started_ts)}</td>
                  <td className="px-3 py-2">{m.alert_counts ? (
                    <span className="flex gap-2 font-mono text-xs">{ALERT_TYPES.map((t) => <span key={t} className={cn(TYPE_TEXT[t])}>{t[0].toUpperCase()}{m.alert_counts![t]}</span>)}</span>) : "—"}</td>
                  <td className="tabular px-3 py-2 font-mono">{m.distance_m == null ? "—" : `${Math.round(m.distance_m)} m`}</td>
                  <td className="px-3 py-2">
                    <span className="flex flex-wrap justify-end gap-0.5">
                      <a className={link} href={`#/replay/${m.id}`}><History size={13} /> Replay</a>
                      <a className={link} href={`#/analytics/${m.id}`}><ChartColumn size={13} /> Analytics</a>
                      <a className={link} href={reportUrl(m.id)} target="_blank" rel="noopener"><FileText size={13} /> Report</a>
                      <a className={link} href={exportUrl(m.id, "csv")} download>CSV</a>
                      <a className={link} href={exportUrl(m.id, "geojson")} download>GeoJSON</a>
                      <a className={link} href={exportUrl(m.id, "kml")} download>KML</a>
                    </span>
                  </td>
                </tr>
              ))}
              {!missions.length && <tr><td colSpan={6} className="px-3 py-8 text-center text-muted">{q.isLoading ? "Loading…" : "No missions yet."}</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
