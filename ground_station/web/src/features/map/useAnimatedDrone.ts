import { useEffect, useRef, useState } from "react";
import { lerpAngle, type DronePose } from "../../lib/geo";

/** Glides the drone marker from its current pose to each new target over `durationMs` (rAF). */
export function useAnimatedDrone(target: DronePose | null, durationMs = 1000): DronePose | null {
  const [pose, setPose] = useState<DronePose | null>(target);
  const cur = useRef<DronePose | null>(target);
  const raf = useRef<number | null>(null);

  useEffect(() => {
    if (raf.current != null) cancelAnimationFrame(raf.current);
    if (!target) { cur.current = null; setPose(null); return; }
    const from = cur.current;
    if (!from) { cur.current = target; setPose(target); return; }
    const t0 = performance.now();
    const step = () => {
      const f = Math.min(1, (performance.now() - t0) / durationMs);
      const next: DronePose = {
        lat: from.lat + (target.lat - from.lat) * f,
        lon: from.lon + (target.lon - from.lon) * f,
        course: from.course != null && target.course != null ? lerpAngle(from.course, target.course, f)
          : target.course ?? from.course,
      };
      cur.current = f >= 1 ? target : next;
      setPose(cur.current);
      raf.current = f < 1 ? requestAnimationFrame(step) : null;
    };
    raf.current = requestAnimationFrame(step);
    return () => { if (raf.current != null) cancelAnimationFrame(raf.current); };
    // re-run only when the target values change
  }, [target?.lat, target?.lon, target?.course, durationMs]); // eslint-disable-line react-hooks/exhaustive-deps

  return pose;
}
