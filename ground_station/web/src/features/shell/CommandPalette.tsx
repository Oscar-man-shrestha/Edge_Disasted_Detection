import { Command } from "cmdk";
import { useMemo, useState } from "react";
import { exportUrl, reportUrl } from "../../lib/api";
import { fmtClock, fmtCoord } from "../../lib/format";
import { parseCoords } from "../../lib/geo";
import { sortAlerts, useLive } from "../../store/live";
import { useMapCommand, useOverlays, usePrefs, useSelection } from "../../store/ui";

const go = (hash: string) => { window.location.hash = hash; };

export function CommandPalette() {
  const open = useOverlays((s) => s.palette);
  const setOverlays = useOverlays((s) => s.set);
  const mission = useLive((s) => s.mission);
  const alerts = useLive((s) => s.alerts);
  const prefs = usePrefs((s) => s.prefs);
  const setPrefs = usePrefs((s) => s.set);
  const recent = useMemo(() => sortAlerts(Object.values(alerts)).slice(0, 20), [alerts]);
  const [search, setSearch] = useState("");
  const coords = parseCoords(search);
  const close = () => { setOverlays({ palette: false }); setSearch(""); };
  const run = (f: () => void) => () => { f(); close(); };
  const item = "flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-sm aria-selected:bg-surface-3";
  const group = "px-1 py-1 [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:pb-1 [&_[cmdk-group-heading]]:pt-2 [&_[cmdk-group-heading]]:text-[11px] [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wide [&_[cmdk-group-heading]]:text-muted";

  return (
    <Command.Dialog open={open} onOpenChange={(o) => setOverlays({ palette: o })} label="Command palette"
      overlayClassName="fixed inset-0 z-[3000] bg-black/55"
      contentClassName="fixed left-1/2 top-[12vh] z-[3001] w-[min(640px,calc(100vw-24px))] -translate-x-1/2 overflow-hidden rounded-2xl border border-line bg-surface text-text shadow-panel">
      <Command.Input placeholder="Type a command or search…  (or coordinates: 12.97, 77.59)" autoFocus
        value={search} onValueChange={setSearch}
        className="w-full border-b border-line bg-transparent px-4 py-3 text-sm outline-none placeholder:text-muted" />
      <Command.List className="max-h-[60vh] overflow-y-auto p-1">
        <Command.Empty className="px-4 py-6 text-center text-sm text-muted">No results.</Command.Empty>
        {coords && (
          <Command.Group heading="Coordinates" className={group}>
            {/* value = the typed text, so cmdk always keeps this item for coordinate input */}
            <Command.Item value={search} className={item}
              onSelect={run(() => { go("#/live"); useMapCommand.getState().send({ type: "goto", ...coords }); })}>
              Go to <span className="tabular font-mono">{fmtCoord(coords.lat, coords.lon)}</span>
            </Command.Item>
          </Command.Group>
        )}
        <Command.Group heading="Go to" className={group}>
          <Command.Item className={item} onSelect={run(() => go("#/live"))}>Live</Command.Item>
          <Command.Item className={item} onSelect={run(() => go(`#/replay/${mission?.id ?? ""}`))}>Replay current mission</Command.Item>
          <Command.Item className={item} onSelect={run(() => go(`#/analytics/${mission?.id ?? ""}`))}>Analytics</Command.Item>
          <Command.Item className={item} onSelect={run(() => go("#/missions"))}>Missions</Command.Item>
        </Command.Group>
        <Command.Group heading="Mission" className={group}>
          <Command.Item className={item} onSelect={run(() => setOverlays({ newMission: true }))}>New mission…</Command.Item>
          {mission && (["csv", "geojson", "kml"] as const).map((f) => (
            <Command.Item key={f} className={item} onSelect={run(() => { window.location.href = exportUrl(mission.id, f); })}>
              Export {f.toUpperCase()}
            </Command.Item>
          ))}
          {mission && <Command.Item className={item} onSelect={run(() => window.open(reportUrl(mission.id), "_blank", "noopener"))}>Open printable report</Command.Item>}
        </Command.Group>
        <Command.Group heading="View" className={group}>
          <Command.Item className={item} onSelect={run(() => setPrefs({ map3d: !prefs.map3d }))}>{prefs.map3d ? "Switch to 2D map" : "Switch to 3D map"}</Command.Item>
          <Command.Item className={item} onSelect={run(() => setPrefs({ follow: !prefs.follow }))}>{prefs.follow ? "Stop following drone" : "Follow drone"}</Command.Item>
          <Command.Item className={item} onSelect={run(() => useMapCommand.getState().send({ type: "north" }))}>North up</Command.Item>
          <Command.Item className={item} onSelect={run(() => useMapCommand.getState().send({ type: "fit" }))}>Fit all on map</Command.Item>
          <Command.Item className={item} onSelect={run(() => setPrefs({ theme: prefs.theme === "dark" ? "light" : "dark" }))}>Toggle dark / light theme</Command.Item>
          <Command.Item className={item} onSelect={run(() => setPrefs({ mute: !prefs.mute }))}>{prefs.mute ? "Unmute alert sounds" : "Mute alert sounds"}</Command.Item>
          <Command.Item className={item} onSelect={run(() => setOverlays({ help: true }))}>Keyboard shortcuts</Command.Item>
        </Command.Group>
        {recent.length > 0 && (
          <Command.Group heading="Alerts" className={group}>
            {recent.map((a) => (
              <Command.Item key={a.id} value={`alert ${a.id} ${a.type} ${a.status}`} className={item}
                onSelect={run(() => {
                  useSelection.getState().select(a.id);
                  go("#/live");
                  if (a.lat != null && a.lon != null) useMapCommand.getState().send({ type: "flyTo", lat: a.lat, lon: a.lon });
                })}>
                <span className="capitalize">{a.type}</span>
                <span className="text-muted">#{a.id} · {Math.round(a.conf * 100)}% · {a.status} · {fmtClock(a.received_at)}</span>
              </Command.Item>
            ))}
          </Command.Group>
        )}
      </Command.List>
    </Command.Dialog>
  );
}
