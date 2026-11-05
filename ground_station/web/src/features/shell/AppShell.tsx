import { Router } from "wouter";
import { useHashLocation } from "wouter/use-hash-location";
import { toast } from "sonner";
import { updateAlert } from "../../lib/api";
import type { Alert, AlertStatus } from "../../lib/types";
import { useShortcuts } from "../../hooks/useShortcuts";
import { useTheme } from "../../hooks/useTheme";
import { AppRoutes } from "../../routes";
import { useLive } from "../../store/live";
import { useMapCommand, useOverlays, usePrefs, useSelection } from "../../store/ui";
import { TooltipProvider } from "../../ui/Tooltip";
import { CommandBar } from "./CommandBar";
import { CommandPalette } from "./CommandPalette";
import { NavRail } from "./NavRail";
import { Notifier } from "./Notifier";
import { ShortcutHelp } from "./ShortcutHelp";

/** What the A / R shortcut should set, or null: never reopens a resolved alert. */
export function shortcutStatus(a: Alert | undefined, key: "a" | "r"): AlertStatus | null {
  if (!a) return null;
  if (key === "a") return a.status === "new" ? "acknowledged" : null;
  return a.status === "resolved" ? null : "resolved";
}

async function shortcutAlert(key: "a" | "r") {
  if (document.querySelector('[role="dialog"]')) return;        // never act behind an open dialog
  const id = useSelection.getState().selectedId;
  const target = id == null ? undefined : useLive.getState().alerts[id];
  const status = shortcutStatus(target, key);
  if (!status || id == null) return;
  try {
    const a = await updateAlert(id, { status });
    useLive.getState().applyEvent("alert_update", { alert: a });
  } catch (e) { toast.error(`Update failed: ${(e as Error).message}`); }
}

export function AppShell() {
  useTheme();
  const overlays = useOverlays((s) => s.set);
  const prefs = usePrefs((s) => s.prefs);
  const setPrefs = usePrefs((s) => s.set);
  useShortcuts({
    "mod+k": () => overlays({ palette: true }),
    "?": () => overlays({ help: true }),
    a: () => shortcutAlert("a"),
    r: () => shortcutAlert("r"),
    f: () => setPrefs({ follow: !prefs.follow }),
    "3": () => setPrefs({ map3d: !prefs.map3d }),
    n: () => useMapCommand.getState().send({ type: "north" }),
  });
  return (
    <TooltipProvider>
      <Router hook={useHashLocation}>
        <div className="flex h-full flex-col bg-bg text-text">
          <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:z-[5000] focus:m-2 focus:rounded focus:bg-surface focus:p-2">Skip to content</a>
          <CommandBar />
          <div className="flex min-h-0 flex-1">
            <NavRail />
            <main id="main" className="relative min-h-0 min-w-0 flex-1 pb-[60px] md:pb-0">
              <AppRoutes />
            </main>
          </div>
        </div>
        <Notifier />
        <CommandPalette />
        <ShortcutHelp />
      </Router>
    </TooltipProvider>
  );
}
