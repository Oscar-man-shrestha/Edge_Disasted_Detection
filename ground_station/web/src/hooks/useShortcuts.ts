import { useEffect, useRef } from "react";

const TYPING = 'input, textarea, select, [contenteditable=""], [contenteditable="true"]';

function keyName(e: KeyboardEvent): string {
  if (e.key === " ") return "space";
  return e.key.toLowerCase();
}

/** Global single-key shortcuts. Ignored while typing or with modifiers, except mod+k. */
export function useShortcuts(map: Record<string, () => void>): void {
  const ref = useRef(map);
  ref.current = map;
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const mod = e.metaKey || e.ctrlKey;
      const key = keyName(e);
      if (mod && key === "k") {
        const f = ref.current["mod+k"];
        if (f) { e.preventDefault(); f(); }
        return;
      }
      if (mod || e.altKey) return;
      const target = e.target as Element | null;
      if (target && typeof target.closest === "function" && target.closest(TYPING)) return;
      const f = ref.current[key];
      if (f) { e.preventDefault(); f(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
}
