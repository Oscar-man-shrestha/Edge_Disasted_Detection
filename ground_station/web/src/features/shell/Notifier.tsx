import { useEffect, useMemo, useState } from "react";
import { toast, Toaster } from "sonner";
import { fmtCoord, fmtClock } from "../../lib/format";
import type { Alert } from "../../lib/types";
import { useLive } from "../../store/live";
import { onNewAlert } from "../../store/notify";
import { useMapCommand, usePrefs, useSelection } from "../../store/ui";
import { PersonBanner } from "./PersonBanner";
import { playTones, TONES } from "./sound";

/** Toasts, sounds, tab title and screen-reader announcements for new alerts. */
export function Notifier() {
  const [announce, setAnnounce] = useState("");
  const alerts = useLive((s) => s.alerts);
  const newCount = useMemo(() => Object.values(alerts).filter((a) => a.status === "new").length, [alerts]);

  useEffect(() => onNewAlert((a: Alert) => {
    const pct = Math.round(a.conf * 100);
    if (!usePrefs.getState().prefs.mute) playTones([...TONES[a.type]]);
    setAnnounce(`New ${a.type} alert, ${pct} percent, ${fmtCoord(a.lat, a.lon)}`);
    toast(`New ${a.type} alert · ${pct}%`, {
      description: `${fmtCoord(a.lat, a.lon)} · ${fmtClock(a.received_at)}`,
      className: `gs-toast gs-toast-${a.type}`,
      action: {
        label: "View",
        onClick: () => {
          useSelection.getState().select(a.id);
          if (a.lat != null && a.lon != null) useMapCommand.getState().send({ type: "flyTo", lat: a.lat, lon: a.lon });
        },
      },
    });
  }), []);

  useEffect(() => {
    document.title = newCount ? `(${newCount}) New alerts · Ground Station` : "Ground Station";
  }, [newCount]);

  return (
    <>
      <PersonBanner />
      <div aria-live="assertive" className="sr-only">{announce}</div>
      <Toaster position="bottom-right" theme="system" richColors={false} closeButton
        toastOptions={{ classNames: { toast: "!bg-surface-2 !text-text !border-line" } }} />
    </>
  );
}
