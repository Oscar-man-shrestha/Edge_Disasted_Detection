import { useQuery } from "@tanstack/react-query";
import { FastForward, Pause, Play, Radio, Rewind } from "lucide-react";
import { useEffect, useMemo, useReducer, useRef } from "react";
import { getMissions, getTimeline } from "../../lib/api";
import type { Timeline as TimelineData } from "../../lib/types";
import { fmtDuration } from "../../lib/format";
import { useShortcuts } from "../../hooks/useShortcuts";
import { useSelection } from "../../store/ui";
import { Button } from "../../ui/Button";
import { Panel } from "../../ui/Panel";
import { Segmented } from "../../ui/Segmented";
import { MissionMap } from "../map/MissionMap";
import { ErrorBoundary } from "../shell/ErrorBoundary";
import { MissionPicker } from "./MissionPicker";
import { alertsAt, alertTime, bounds, playback, stateAt, type PlayAction, type PlayState, type Speed } from "./replay";
import { ReplaySidePanel } from "./ReplaySidePanel";
import { Timeline } from "./Timeline";

export default function ReplayView({ missionId }: { missionId?: number }) {
  const missions = useQuery({ queryKey: ["missions"], queryFn: getMissions });
  const id = missionId ?? missions.data?.[missions.data.length - 1]?.id;
  const tlq = useQuery({
    queryKey: ["timeline", id], queryFn: () => getTimeline(id!), enabled: id != null,
    refetchInterval: (q) => (q.state.data && q.state.data.mission.ended_ts == null ? 30_000 : false),
  });
  return (
    <div className="relative flex h-full flex-col">
      <h1 className="sr-only">Replay</h1>
      <div className="flex items-center gap-2 border-b border-line bg-surface px-3 py-2">
        <MissionPicker value={id} missions={missions.data ?? []} route="replay" />
      </div>
      {!tlq.data ? (
        <div className="grid flex-1 place-items-center text-sm text-muted">{tlq.isError ? "Could not load this mission." : "Loading mission…"}</div>
      ) : <ReplayBody key={tlq.data.mission.id} tl={tlq.data} />}
    </div>
  );
}

function ReplayBody({ tl }: { tl: TimelineData }) {
  const b = useMemo(() => bounds(tl), [tl]);
  const [ps, dispatch] = useReducer((s: PlayState, a: PlayAction) => playback.reduce(s, a, b), b, playback.init);
  const select = useSelection((s) => s.select);
  const last = useRef<number | null>(null);
  useEffect(() => {
    if (!ps.playing) { last.current = null; return; }
    let raf = 0;
    const loop = (now: number) => {
      if (last.current != null) dispatch({ type: "tick", dtMs: now - last.current });
      last.current = now;
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [ps.playing]);
  useShortcuts({
    space: () => dispatch({ type: "toggle" }),
    arrowleft: () => dispatch({ type: "step", by: -10 }),
    arrowright: () => dispatch({ type: "step", by: 10 }),
  });

  const st = useMemo(() => stateAt(tl, ps.t), [tl, ps.t]);
  const visible = useMemo(() => alertsAt(tl, ps.t), [tl, ps.t]);
  const latest = useMemo(() => [...visible].sort((x, y) => alertTime(y, tl) - alertTime(x, tl))[0] ?? null, [visible, tl]);
  const empty = !tl.telemetry.length && !tl.track.length;
  const ongoing = tl.mission.ended_ts == null;

  return (
    <div className="relative min-h-0 flex-1">
      <div className="absolute inset-0">
        <ErrorBoundary name="Replay map">
          <MissionMap mode="replay" drone={st.drone} trail={st.trail} alerts={visible} onSelectAlert={select} />
        </ErrorBoundary>
      </div>
      {empty && (
        <div role="status" className="absolute left-1/2 top-4 z-10 -translate-x-1/2 rounded-xl border border-line bg-surface/95 px-4 py-2 text-sm shadow-panel">
          No flight data recorded for this mission{tl.alerts.length ? ` — ${tl.alerts.length} alert(s) shown at mission start` : ""}
        </div>
      )}
      <div className="absolute right-[60px] top-3 hidden max-h-[calc(100%-150px)] w-[300px] lg:block">
        <ReplaySidePanel sample={st.sample} latest={latest} t={ps.t} />
      </div>
      <Panel className="absolute inset-x-3 bottom-3 z-10 px-4 py-3 md:left-3 lg:right-[372px]">
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="primary" size="icon" aria-label={ps.playing ? "Pause" : "Play"} onClick={() => dispatch({ type: "toggle" })}>
            {ps.playing ? <Pause size={16} /> : <Play size={16} />}
          </Button>
          <Button size="icon" aria-label="Back 10 seconds" onClick={() => dispatch({ type: "step", by: -10 })}><Rewind size={14} /></Button>
          <Button size="icon" aria-label="Forward 10 seconds" onClick={() => dispatch({ type: "step", by: 10 })}><FastForward size={14} /></Button>
          <Segmented<string> label="Playback speed" value={String(ps.speed)} onChange={(v) => dispatch({ type: "setSpeed", speed: Number(v) as Speed })}
            options={[{ value: "1", label: "1×" }, { value: "4", label: "4×" }, { value: "16", label: "16×" }]} />
          <span className="tabular ml-1 font-mono text-sm">{fmtDuration(ps.t - b.start)}</span>
          <span className="text-xs text-muted">{visible.length} / {tl.alerts.length} alerts</span>
          {ongoing && (
            <Button size="sm" className="ml-auto" onClick={() => { window.location.hash = "#/live"; }}>
              <Radio size={14} /> Jump to live
            </Button>
          )}
        </div>
        <div className="mt-2"><Timeline tl={tl} b={b} t={ps.t} onSeek={(t) => dispatch({ type: "seek", t })} /></div>
      </Panel>
    </div>
  );
}
