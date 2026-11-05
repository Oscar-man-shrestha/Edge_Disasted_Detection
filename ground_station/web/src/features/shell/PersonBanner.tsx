import { TriangleAlert } from "lucide-react";
import { useMemo } from "react";
import { useLive } from "../../store/live";
import { useMapCommand, useSelection } from "../../store/ui";

/** Stays visible while any person alert of this mission is still unacknowledged. */
export function PersonBanner() {
  const alerts = useLive((s) => s.alerts);
  const open = useMemo(
    () => Object.values(alerts).filter((a) => a.type === "person" && a.status === "new").sort((a, b) => b.id - a.id),
    [alerts],
  );
  if (!open.length) return null;
  const a = open[0];
  return (
    <div role="alert" aria-label={`Person detected — ${open.length} unacknowledged`}
      className="pointer-events-auto fixed bottom-[164px] left-1/2 z-[2000] flex w-max max-w-[calc(100vw-24px)] -translate-x-1/2 items-center gap-3 rounded-xl border border-critical bg-critical px-4 py-2 text-sm font-semibold text-white shadow-panel md:bottom-auto md:top-16">
      <TriangleAlert size={18} aria-hidden />
      <span>Person detected{open.length > 1 ? ` (${open.length})` : ""} — acknowledge to clear</span>
      <button type="button" className="rounded-md bg-white/20 px-2 py-0.5 text-xs hover:bg-white/30"
        onClick={() => {
          useSelection.getState().select(a.id);
          if (a.lat != null && a.lon != null) useMapCommand.getState().send({ type: "flyTo", lat: a.lat, lon: a.lon });
          window.location.hash = "#/live";
        }}>
        Show
      </button>
    </div>
  );
}
