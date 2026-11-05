export interface LatLon { lat: number; lon: number }
export interface Positioned { t: number; lat: number | null; lon: number | null; course_deg?: number | null }
export interface DronePose { lat: number; lon: number; course: number | null }

const M_PER_DEG = 111320;

/** Equirectangular distance in metres (same formula as the station backend). */
export function distanceM(a: LatLon, b: LatLon): number {
  const dlat = (b.lat - a.lat) * M_PER_DEG;
  const dlon = (b.lon - a.lon) * M_PER_DEG * Math.cos(((a.lat + b.lat) / 2) * (Math.PI / 180));
  return Math.hypot(dlat, dlon);
}

export function pathDistanceM(pts: LatLon[]): number {
  let d = 0;
  for (let i = 1; i < pts.length; i++) d += distanceM(pts[i - 1], pts[i]);
  return d;
}

/** Interpolate between two headings the short way round, result in [0, 360). */
export function lerpAngle(a: number, b: number, f: number): number {
  const diff = ((((b - a) % 360) + 540) % 360) - 180;
  return (((a + diff * f) % 360) + 360) % 360;
}

const valid = (s: Positioned): s is Positioned & LatLon =>
  typeof s.lat === "number" && Number.isFinite(s.lat) && typeof s.lon === "number" && Number.isFinite(s.lon);

function courseOf(s: Positioned): number | null {
  return typeof s.course_deg === "number" && Number.isFinite(s.course_deg) ? s.course_deg : null;
}

/** Drone pose at time t from time-ordered samples; clamps outside the range; null if no usable sample. */
export function interpolateAt(samples: Positioned[], t: number): DronePose | null {
  const pts = samples.filter(valid);
  if (!pts.length) return null;
  if (t <= pts[0].t) return { lat: pts[0].lat, lon: pts[0].lon, course: courseOf(pts[0]) };
  const last = pts[pts.length - 1];
  if (t >= last.t) return { lat: last.lat, lon: last.lon, course: courseOf(last) };
  let lo = 0, hi = pts.length - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (pts[mid].t <= t) lo = mid; else hi = mid;
  }
  const a = pts[lo], b = pts[hi];
  const f = b.t === a.t ? 0 : (t - a.t) / (b.t - a.t);
  const ca = courseOf(a), cb = courseOf(b);
  return {
    lat: a.lat + (b.lat - a.lat) * f,
    lon: a.lon + (b.lon - a.lon) * f,
    course: ca !== null && cb !== null ? lerpAngle(ca, cb, f) : (ca ?? cb),
  };
}
