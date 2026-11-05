import { Bell, BellOff, ChevronDown, Command, Download, FileText, Moon, Plus, Sun, SunMoon } from "lucide-react";
import { useMemo, useState } from "react";
import { exportUrl, newMission, reportUrl } from "../../lib/api";
import { fmtDuration } from "../../lib/format";
import { ALERT_TYPES } from "../../lib/types";
import { useServerNow } from "../../hooks/useServerNow";
import { useLive } from "../../store/live";
import { useOverlays, usePrefs } from "../../store/ui";
import { TYPE_BG } from "../../ui/Badge";
import { Button } from "../../ui/Button";
import { DialogContent, DialogRoot } from "../../ui/Dialog";
import { MenuContent, MenuItem, MenuLabel, MenuRoot, MenuSeparator, MenuTrigger } from "../../ui/Menu";
import { Tip } from "../../ui/Tooltip";
import { cn } from "../../ui/cn";
import { toast } from "sonner";
import { GpsChip, LinkPill } from "./LinkPill";

export function CommandBar() {
  const mission = useLive((s) => s.mission);
  const missions = useLive((s) => s.missions);
  const alerts = useLive((s) => s.alerts);
  const now = useServerNow();
  const prefs = usePrefs((s) => s.prefs);
  const setPrefs = usePrefs((s) => s.set);
  const overlays = useOverlays();
  const counts = useMemo(() => {
    const c = Object.fromEntries(ALERT_TYPES.map((t) => [t, { fresh: 0, total: 0 }])) as Record<string, { fresh: number; total: number }>;
    Object.values(alerts).forEach((a) => { c[a.type].total++; if (a.status === "new") c[a.type].fresh++; });
    return c;
  }, [alerts]);
  const nextTheme = prefs.theme === "system" ? "dark" : prefs.theme === "dark" ? "light" : "system";
  const ThemeIcon = prefs.theme === "dark" ? Moon : prefs.theme === "light" ? Sun : SunMoon;

  return (
    <header className="z-[1000] flex flex-wrap items-center gap-2 border-b border-line bg-surface px-3 py-2 md:flex-nowrap">
      <div className="mr-1 flex items-center gap-2 font-semibold tracking-tight">
        <span aria-hidden className="h-5 w-5 rounded-md bg-[conic-gradient(var(--gs-fire),var(--gs-person),var(--gs-smoke),var(--gs-fire))]" />
        <span className="hidden lg:inline">Ground Station</span>
      </div>

      <MenuRoot>
        <MenuTrigger asChild>
          <button type="button" className="flex h-9 items-center gap-2 rounded-lg px-2 text-left hover:bg-surface-2" aria-label="Missions">
            <span className="flex flex-col leading-tight">
              <span className="max-w-[160px] truncate text-[11px] text-text-2">{mission?.name ?? "—"}</span>
              <span className="tabular font-mono text-sm font-semibold">
                {mission ? fmtDuration((mission.ended_ts ?? now) - mission.started_ts) : "00:00:00"}
              </span>
            </span>
            <ChevronDown size={14} className="text-muted" />
          </button>
        </MenuTrigger>
        <MenuContent align="start">
          <MenuLabel>Missions</MenuLabel>
          {[...missions].reverse().slice(0, 8).map((m) => (
            <MenuItem key={m.id} onSelect={() => { window.location.hash = `#/replay/${m.id}`; }}>
              <span className="flex-1 truncate">{m.name}</span>
              {m.id === mission?.id && <span className="text-[11px] text-good">current</span>}
            </MenuItem>
          ))}
          <MenuSeparator />
          <MenuItem onSelect={() => { window.location.hash = "#/missions"; }}>All missions…</MenuItem>
        </MenuContent>
      </MenuRoot>

      <LinkPill />
      <GpsChip />

      <div className="hidden items-center gap-1.5 md:flex" aria-label="Alert counts (new / total)">
        {ALERT_TYPES.map((t) => (
          <span key={t} title={`${t}: ${counts[t].fresh} new of ${counts[t].total}`}
            className={cn("tabular inline-flex h-8 items-center gap-1.5 rounded-lg border bg-surface-2 px-2 text-xs",
              counts[t].fresh ? "border-serious" : "border-line")}>
            <i aria-hidden className={cn("h-2 w-2 rounded-sm", TYPE_BG[t])} />
            <span className="capitalize text-text-2">{t}</span>
            <b className="font-mono">{counts[t].fresh}/{counts[t].total}</b>
          </span>
        ))}
      </div>

      <div className="flex-1" />

      <Tip label={prefs.mute ? "Sounds off" : "Sounds on"}>
        <Button variant="ghost" size="icon" aria-pressed={!prefs.mute} aria-label={prefs.mute ? "Unmute alerts" : "Mute alerts"}
          onClick={() => setPrefs({ mute: !prefs.mute })}>
          {prefs.mute ? <BellOff size={16} /> : <Bell size={16} />}
        </Button>
      </Tip>
      <Tip label={`Theme: ${prefs.theme}`}>
        <Button variant="ghost" size="icon" aria-label={`Theme: ${prefs.theme}`} onClick={() => setPrefs({ theme: nextTheme })}>
          <ThemeIcon size={16} />
        </Button>
      </Tip>
      {/* desktop-only: a wrapper hides them (Button's own inline-flex would beat a "hidden" class) */}
      <span className="hidden items-center gap-2 sm:inline-flex">
        <Button variant="ghost" aria-label="Command palette" onClick={() => overlays.set({ palette: true })}>
          <Command size={14} /><span className="text-xs text-muted">K</span>
        </Button>
        <Button onClick={() => overlays.set({ newMission: true })}>
          <Plus size={14} /> New mission
        </Button>
      </span>
      <MenuRoot>
        <MenuTrigger asChild>
          <Button variant="primary"><Download size={14} /> Export</Button>
        </MenuTrigger>
        <MenuContent>
          {mission && (<>
            <MenuItem asChild><a href={exportUrl(mission.id, "csv")} download>CSV (spreadsheet)</a></MenuItem>
            <MenuItem asChild><a href={exportUrl(mission.id, "geojson")} download>GeoJSON (GIS)</a></MenuItem>
            <MenuItem asChild><a href={exportUrl(mission.id, "kml")} download>KML (Google Earth)</a></MenuItem>
            <MenuSeparator />
            <MenuItem asChild><a href={reportUrl(mission.id)} target="_blank" rel="noopener"><FileText size={14} /> Printable report</a></MenuItem>
          </>)}
        </MenuContent>
      </MenuRoot>

      <NewMissionDialog open={overlays.newMission} onOpenChange={(o) => overlays.set({ newMission: o })} />
    </header>
  );
}

function NewMissionDialog({ open, onOpenChange }: { open: boolean; onOpenChange(o: boolean): void }) {
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <DialogRoot open={open} onOpenChange={onOpenChange}>
      <DialogContent title="Start a new mission" description="The current mission is closed. Its alerts, track and history stay available in Missions.">
        <form onSubmit={async (e) => {
          e.preventDefault(); setBusy(true);
          try { const m = await newMission(name.trim() || undefined); toast(`Mission started: ${m.name}`); onOpenChange(false); setName(""); }
          catch (err) { toast.error(`Could not start mission: ${(err as Error).message}`); }
          finally { setBusy(false); }
        }}>
          <label className="text-sm text-text-2" htmlFor="mission-name">Mission name</label>
          <input id="mission-name" autoFocus value={name} onChange={(e) => setName(e.target.value)} maxLength={80}
            placeholder="e.g. Site A – north ridge"
            className="mt-1 w-full rounded-lg border border-line bg-surface-2 px-3 py-2 text-sm outline-none focus:border-accent" />
          <div className="mt-4 flex justify-end gap-2">
            <Button variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button variant="primary" type="submit" disabled={busy}>Start mission</Button>
          </div>
        </form>
      </DialogContent>
    </DialogRoot>
  );
}
