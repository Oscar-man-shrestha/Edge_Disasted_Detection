import { snapUrl } from "../../lib/api";
import { fmtClock, fmtNum } from "../../lib/format";
import type { Alert, TelemetrySample } from "../../lib/types";
import { TypeBadge } from "../../ui/Badge";
import { Panel, PanelHeader } from "../../ui/Panel";

export function ReplaySidePanel({ sample, latest, t }: { sample: TelemetrySample | null; latest: Alert | null; t: number }) {
  const rows: [string, string][] = [
    ["Clock", fmtClock(t)], ["Pipeline", sample?.state?.toUpperCase() ?? "—"], ["Speed", `${fmtNum(sample?.speed_mps, 1)} m/s`],
    ["Heading", `${fmtNum(sample?.course_deg)}°`], ["Altitude", `${fmtNum(sample?.alt_m)} m`], ["Satellites", fmtNum(sample?.sats)],
    ["Frame rate", `${fmtNum(sample?.fps, 1)} fps`], ["Power", sample?.power_mw != null ? `${(sample.power_mw / 1000).toFixed(1)} W` : "—"],
    ["CPU / GPU °C", `${fmtNum(sample?.cpu_temp_c)} / ${fmtNum(sample?.gpu_temp_c)}`],
    ["YOLO runs / skipped", `${fmtNum(sample?.stage2_runs)} / ${fmtNum(sample?.stage2_skipped)}`],
  ];
  return (
    <Panel className="flex max-h-full flex-col overflow-hidden">
      <PanelHeader title="At this moment" />
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 px-3 text-sm">
        {rows.map(([k, v]) => (<div key={k} className="contents"><dt className="text-muted">{k}</dt><dd className="tabular text-right font-mono">{v}</dd></div>))}
      </dl>
      <PanelHeader title="Latest alert" className="mt-2" />
      <div className="px-3 pb-3">
        {latest ? (
          <div>
            <div className="mb-1.5 flex items-center gap-2"><TypeBadge type={latest.type} /><b className="font-mono text-sm">{Math.round(latest.conf * 100)}%</b>
              <span className="ml-auto text-xs text-muted">#{latest.id}</span></div>
            {latest.snapshot ? <img src={snapUrl(latest.snapshot)} alt={`${latest.type} alert ${latest.id}`} className="w-full rounded-lg border border-line" />
              : <p className="text-sm text-muted">No snapshot</p>}
          </div>
        ) : <p className="text-sm text-muted">No alerts yet at this point.</p>}
      </div>
    </Panel>
  );
}
