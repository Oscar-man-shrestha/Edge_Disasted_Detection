import { Bell, Camera, Gauge as GaugeIcon } from "lucide-react";
import { useMemo, useState } from "react";
import { useServerNow } from "../../hooks/useServerNow";
import type { DronePose } from "../../lib/geo";
import { isNum } from "../../lib/format";
import { linkState, useLive, visibleAlerts } from "../../store/live";
import { usePrefs, useSelection } from "../../store/ui";
import { Button } from "../../ui/Button";
import { DialogContent, DialogRoot } from "../../ui/Dialog";
import { Panel } from "../../ui/Panel";
import { AlertDrawer } from "../alerts/AlertDrawer";
import { MissionMap } from "../map/MissionMap";
import { ErrorBoundary } from "../shell/ErrorBoundary";
import { CameraCard } from "./CameraCard";
import { FlightHud } from "./FlightHud";

export default function LiveView() {
  const telemetry = useLive((s) => s.telemetry);
  const telemetryAt = useLive((s) => s.telemetryAt);
  const track = useLive((s) => s.track);
  const alerts = useLive((s) => s.alerts);
  const prefs = usePrefs((s) => s.prefs);
  const { selectedId, select } = useSelection();
  const now = useServerNow(1000);
  const [sheet, setSheet] = useState<null | "camera" | "flight" | "alerts">(null);

  const g = telemetry?.gps;
  const live = linkState({ telemetryAt }, now).state === "live";
  const hasFix = g?.fix === true && isNum(g.lat) && isNum(g.lon);
  const last = track[track.length - 1];
  const drone: DronePose | null = hasFix ? { lat: g!.lat!, lon: g!.lon!, course: isNum(g!.course_deg) ? g!.course_deg! : null }
    : last ? { lat: last.lat, lon: last.lon, course: null } : null;
  const trail = useMemo(() => track.map((p) => [p.lon, p.lat] as [number, number]), [track]);
  const mapAlerts = useMemo(() => visibleAlerts({ alerts }, prefs), [alerts, prefs]);
  const newCount = Object.values(alerts).filter((a) => a.status === "new").length;

  return (
    <div className="relative h-full w-full overflow-hidden">
      <h1 className="sr-only">Live</h1>
      <div className="absolute inset-0">
        <ErrorBoundary name="Map">
          <MissionMap mode="live" drone={drone} droneStale={!hasFix || !live} trail={trail} alerts={mapAlerts}
            selectedId={selectedId} onSelectAlert={(id) => { select(id); setSheet((s) => (s ? "alerts" : s)); }} />
        </ErrorBoundary>
      </div>

      {/* tablet / laptop: floating panels */}
      <div className="pointer-events-none absolute inset-y-3 left-3 hidden w-[330px] flex-col gap-3 overflow-y-auto md:flex">
        <div className="pointer-events-auto"><ErrorBoundary name="Camera"><CameraCard /></ErrorBoundary></div>
        <div className="pointer-events-auto"><ErrorBoundary name="Flight"><FlightHud /></ErrorBoundary></div>
      </div>
      <Panel className="absolute inset-y-3 right-[60px] hidden w-[380px] overflow-hidden lg:flex lg:flex-col">
        <ErrorBoundary name="Alerts"><AlertDrawer /></ErrorBoundary>
      </Panel>

      {/* phone and narrow tablet: sheets */}
      <div className="absolute bottom-12 left-1/2 z-10 flex -translate-x-1/2 gap-2 whitespace-nowrap md:bottom-3 lg:hidden">
        <Button className="bg-surface/95 shadow-panel md:hidden" onClick={() => setSheet("camera")}><Camera size={14} /> Camera</Button>
        <Button className="bg-surface/95 shadow-panel md:hidden" onClick={() => setSheet("flight")}><GaugeIcon size={14} /> Flight</Button>
        <Button variant="primary" className="shadow-panel" onClick={() => setSheet("alerts")}>
          <Bell size={14} /> Alerts{newCount ? ` (${newCount})` : ""}
        </Button>
      </div>
      <DialogRoot open={sheet != null} onOpenChange={(o) => !o && setSheet(null)}>
        {sheet && (
          <DialogContent side="bottom" title={sheet === "camera" ? "Camera" : sheet === "flight" ? "Flight" : "Alerts"}>
            <div className="flex max-h-[70vh] min-h-[40vh] flex-col">
              {sheet === "camera" && <CameraCard />}
              {sheet === "flight" && <FlightHud />}
              {sheet === "alerts" && <AlertDrawer />}
            </div>
          </DialogContent>
        )}
      </DialogRoot>
    </div>
  );
}
