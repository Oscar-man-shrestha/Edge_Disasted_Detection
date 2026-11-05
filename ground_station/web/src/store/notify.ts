import type { Alert } from "../lib/types";

type Listener = (a: Alert) => void;
const listeners = new Set<Listener>();

/** A genuinely new alert (live event or missed during a reconnect) -> toast, sound, a11y. */
export function emitNewAlert(a: Alert): void { listeners.forEach((l) => l(a)); }
export function onNewAlert(l: Listener): () => void { listeners.add(l); return () => listeners.delete(l); }
