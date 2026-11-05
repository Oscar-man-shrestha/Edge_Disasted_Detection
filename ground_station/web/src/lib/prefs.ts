import type { AlertStatusFilter, AlertType } from "./types";

export interface Prefs {
  theme: "system" | "dark" | "light";
  mute: boolean;
  follow: boolean;
  map3d: boolean;
  headingUp: boolean;
  types: AlertType[];
  status: AlertStatusFilter;
}

export const DEFAULT_PREFS: Prefs = {
  theme: "system", mute: false, follow: true, map3d: false, headingUp: false,
  types: ["person", "fire", "smoke"], status: "open",
};

const KEY = "gs-prefs-v3";

export function loadPrefs(): Prefs {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? { ...DEFAULT_PREFS, ...JSON.parse(raw) } : { ...DEFAULT_PREFS };
  } catch {
    return { ...DEFAULT_PREFS };
  }
}

export function savePrefs(p: Prefs): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(p));
  } catch {
    /* private mode / quota: preferences are a convenience only */
  }
}
