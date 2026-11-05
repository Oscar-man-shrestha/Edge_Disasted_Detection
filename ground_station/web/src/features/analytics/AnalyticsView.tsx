import * as Tabs from "@radix-ui/react-tabs";
import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { getMissions, getTimeline } from "../../lib/api";
import { fmtDuration, fmtNum } from "../../lib/format";
import { ALERT_TYPES, type Timeline } from "../../lib/types";
import { TYPE_BG } from "../../ui/Badge";
import { cn } from "../../ui/cn";
import { ErrorBoundary } from "../shell/ErrorBoundary";
import { MissionPicker } from "../replay/MissionPicker";
import { bounds } from "../replay/replay";
import { DetectionsChart, FpsChart, PipelineBand, PowerChart, TemperatureChart } from "./charts";
import { KpiTile } from "./KpiTile";
import { detectionsPerMinute, summary } from "./metrics";
import { TelemetryTable } from "./TelemetryTable";

export default function AnalyticsView({ missionId }: { missionId?: number }) {
  const missions = useQuery({ queryKey: ["missions"], queryFn: getMissions });
  const id = missionId ?? missions.data?.[missions.data.length - 1]?.id;
  const tlq = useQuery({
    queryKey: ["timeline", id], queryFn: () => getTimeline(id!), enabled: id != null,
    refetchInterval: (q) => (q.state.data && q.state.data.mission.ended_ts == null ? 30_000 : false),
  });
  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-[1400px] p-4">
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <h1 className="text-xl font-semibold">Analytics</h1>
          <MissionPicker value={id} missions={missions.data ?? []} route="analytics" />
          {tlq.data?.mission.ended_ts == null && tlq.data && <span className="text-xs text-good">live mission · refreshes every 30 s</span>}
        </div>
        {!tlq.data ? <p className="text-sm text-muted">{tlq.isError ? "Could not load this mission." : "Loading…"}</p>
          : <Body tl={tlq.data} />}
      </div>
    </div>
  );
}

function Body({ tl }: { tl: Timeline }) {
  const s = useMemo(() => summary(tl), [tl]);
  const buckets = useMemo(() => detectionsPerMinute(tl), [tl]);
  const total = ALERT_TYPES.reduce((n, t) => n + s.counts[t].total, 0);
  const empty = tl.telemetry.length === 0;
  return (
    <>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <KpiTile testId="kpi-alerts" label="Alerts" value={total}
          sub={<span className="flex gap-2">{ALERT_TYPES.map((t) => (
            <span key={t} className="flex items-center gap-1"><i aria-hidden className={cn("h-2 w-2 rounded-sm", TYPE_BG[t])} />{t} {s.counts[t].open}/{s.counts[t].total}</span>
          ))}</span>} />
        <KpiTile label="Duration" value={fmtDuration(s.durationS)} />
        <KpiTile label="Distance flown" value={`${Math.round(s.distanceM)} m`} />
        <KpiTile testId="kpi-compute-saved" label="Compute saved" value={s.computeSavedPct == null ? "—" : `${Math.round(s.computeSavedPct)}%`}
          sub={`YOLO ran ${fmtNum(s.stage2Runs)} · skipped ${fmtNum(s.stage2Skipped)}`} />
        <KpiTile label="Power" value={s.avgPowerW == null ? "—" : `${s.avgPowerW.toFixed(1)} W`} sub={`peak ${s.peakPowerW == null ? "—" : s.peakPowerW.toFixed(1) + " W"}`} />
        <KpiTile label="Peak temps" value={`${fmtNum(s.peakCpuC)}° / ${fmtNum(s.peakGpuC)}°`} sub="CPU / GPU" />
      </div>
      {empty && <p role="status" className="mt-4 rounded-xl border border-line bg-surface p-4 text-sm text-text-2">No telemetry recorded for this mission</p>}
      <Tabs.Root defaultValue="charts" className="mt-4">
        <Tabs.List aria-label="Analytics view" className="mb-3 inline-flex rounded-lg border border-line bg-surface-2 p-0.5">
          {["charts", "table"].map((v) => (
            <Tabs.Trigger key={v} value={v} className="rounded-md px-3 py-1 text-sm font-semibold capitalize text-text-2 data-[state=active]:bg-surface-3 data-[state=active]:text-text">{v}</Tabs.Trigger>
          ))}
        </Tabs.List>
        <Tabs.Content value="charts">
          <div className="grid gap-3 lg:grid-cols-2">
            <ErrorBoundary name="Detections"><DetectionsChart buckets={buckets} start={bounds(tl).start} /></ErrorBoundary>
            <ErrorBoundary name="Power"><PowerChart rows={tl.telemetry} /></ErrorBoundary>
            <ErrorBoundary name="Temperatures"><TemperatureChart rows={tl.telemetry} /></ErrorBoundary>
            <ErrorBoundary name="Frame rate"><FpsChart rows={tl.telemetry} /></ErrorBoundary>
            <div className="lg:col-span-2"><ErrorBoundary name="Pipeline"><PipelineBand tl={tl} /></ErrorBoundary></div>
          </div>
        </Tabs.Content>
        <Tabs.Content value="table"><TelemetryTable rows={tl.telemetry} /></Tabs.Content>
      </Tabs.Root>
    </>
  );
}
