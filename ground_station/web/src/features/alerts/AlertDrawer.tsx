import { useMemo } from "react";
import { useLive, visibleAlerts } from "../../store/live";
import { usePrefs, useSelection } from "../../store/ui";
import { PanelHeader } from "../../ui/Panel";
import { AlertDetail } from "./AlertDetail";
import { AlertFilters } from "./AlertFilters";
import { AlertList } from "./AlertList";

export function AlertDrawer() {
  const alerts = useLive((s) => s.alerts);
  const prefs = usePrefs((s) => s.prefs);
  const { selectedId, select } = useSelection();
  const list = useMemo(() => visibleAlerts({ alerts }, prefs), [alerts, prefs]);
  const total = Object.keys(alerts).length;
  const selected = selectedId != null ? alerts[selectedId] : undefined;
  return (
    <section aria-label="Alerts" className="flex h-full min-h-0 flex-col">
      <PanelHeader title="Alerts" right={<span className="text-xs text-muted">{list.length} shown · {total} total</span>} />
      {selected ? <AlertDetail alert={selected} onBack={() => select(null)} /> : (
        <>
          <AlertFilters />
          <AlertList alerts={list} selectedId={selectedId} onSelect={select} />
        </>
      )}
    </section>
  );
}
