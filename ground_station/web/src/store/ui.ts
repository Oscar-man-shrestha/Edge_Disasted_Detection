import { create } from "zustand";
import { loadPrefs, savePrefs, type Prefs } from "../lib/prefs";

export const usePrefs = create<{ prefs: Prefs; set(p: Partial<Prefs>): void }>()((set, get) => ({
  prefs: loadPrefs(),
  set(p) {
    const next = { ...get().prefs, ...p };
    savePrefs(next);
    set({ prefs: next });
  },
}));

/** Selected alert (shared by map, drawer, shortcuts, palette). */
export const useSelection = create<{ selectedId: number | null; select(id: number | null): void }>()((set) => ({
  selectedId: null,
  select: (id) => set({ selectedId: id }),
}));

export type MapCommand =
  | { type: "fit" } | { type: "north" } | { type: "flyTo"; lat: number; lon: number };

/** One-shot commands for the map (palette/shortcuts/drawer -> MissionMap). */
export const useMapCommand = create<{ cmd: (MapCommand & { seq: number; at: number }) | null; send(c: MapCommand): void }>()(
  (set, get) => ({ cmd: null, send: (c) => set({ cmd: { ...c, seq: (get().cmd?.seq ?? 0) + 1, at: Date.now() } }) }),
);

export const useOverlays = create<{ palette: boolean; help: boolean; newMission: boolean;
  set(p: Partial<{ palette: boolean; help: boolean; newMission: boolean }>): void }>()((set) => ({
  palette: false, help: false, newMission: false, set: (p) => set(p),
}));
