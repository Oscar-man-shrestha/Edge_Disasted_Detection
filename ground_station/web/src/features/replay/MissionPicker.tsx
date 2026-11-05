import type { Mission } from "../../lib/types";

export function MissionPicker({ value, missions, route }: { value?: number; missions: Mission[]; route: "replay" | "analytics" }) {
  return (
    <label className="flex items-center gap-2 text-sm">
      <span className="text-muted">Mission</span>
      <select value={value ?? ""} onChange={(e) => { window.location.hash = `#/${route}/${e.target.value}`; }}
        className="rounded-lg border border-line bg-surface-2 px-2.5 py-1.5 text-sm">
        {[...missions].reverse().map((m) => (
          <option key={m.id} value={m.id}>{m.name}{m.ended_ts == null ? " (current)" : ""}</option>
        ))}
      </select>
    </label>
  );
}
