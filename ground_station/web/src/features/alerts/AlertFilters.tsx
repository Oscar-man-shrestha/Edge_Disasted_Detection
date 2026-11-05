import type { AlertStatusFilter, AlertType } from "../../lib/types";
import { usePrefs } from "../../store/ui";
import { MultiToggle, Segmented } from "../../ui/Segmented";

export function AlertFilters() {
  const prefs = usePrefs((s) => s.prefs);
  const set = usePrefs((s) => s.set);
  return (
    <div className="flex flex-wrap items-center gap-2 px-3 pb-2">
      <MultiToggle<AlertType> label="Filter by type" value={prefs.types} onChange={(types) => set({ types })}
        options={[{ value: "person", label: "Person", className: "bg-person" }, { value: "fire", label: "Fire", className: "bg-fire" },
          { value: "smoke", label: "Smoke", className: "bg-smoke" }]} />
      <Segmented<AlertStatusFilter> label="Filter by status" value={prefs.status} onChange={(status) => set({ status })}
        options={[{ value: "open", label: "Open" }, { value: "new", label: "New" }, { value: "resolved", label: "Done" }, { value: "all", label: "All" }]} />
    </div>
  );
}
