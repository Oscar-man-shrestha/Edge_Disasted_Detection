import { useEffect, useState } from "react";
import { useLive } from "../store/live";

/** Server time in seconds, re-rendering every `everyMs`. */
export function useServerNow(everyMs = 1000): number {
  const clock = useLive((s) => s.clock);
  const [now, setNow] = useState(() => clock.now());
  useEffect(() => {
    setNow(clock.now());
    const id = setInterval(() => setNow(clock.now()), everyMs);
    return () => clearInterval(id);
  }, [clock, everyMs]);
  return now;
}
