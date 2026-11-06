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

/** Coordinates typed or pasted by an operator, e.g. "12.97, 77.59", "12.97 77.59",
 *  "12.97N 77.59E", "12.97°S, 77.59°W". Latitude first (the usual order); if the first
 *  number cannot be a latitude but the second can, they are swapped. Null if not coordinates. */
export function parseCoords(text: string): LatLon | null {
  const m = text.trim().match(
    /^\(?\s*(-?\d{1,3}(?:\.\d+)?)\s*°?\s*([NSns])?\s*[,;\s]\s*(-?\d{1,3}(?:\.\d+)?)\s*°?\s*([EWew])?\s*\)?$/);
  if (!m) return null;
  let a = Number(m[1]), b = Number(m[3]);
  if (m[2] && /s/i.test(m[2])) a = -Math.abs(a);
  if (m[4] && /w/i.test(m[4])) b = -Math.abs(b);
  if (Math.abs(a) > 90 && Math.abs(b) <= 90 && !m[2] && !m[4]) [a, b] = [b, a];
  if (Math.abs(a) > 90 || Math.abs(b) > 180) return null;
  return { lat: a, lon: b };
}

/** Pixel offsets that fan out markers sharing (about) the same spot into a small ring, so
 *  every one can be clicked. Markers alone at their spot get no entry. Positions closer
 *  than ~1 m (5 decimals) count as the same spot. */
export function spreadOffsets<T extends { id: number; lat: number; lon: number }>(items: T[]):
    { offsets: Map<number, [number, number]>; hubs: (LatLon & { legs: [number, number][] })[] } {
  const groups = new Map<string, T[]>();
  for (const it of items) {
    const k = `${it.lat.toFixed(5)},${it.lon.toFixed(5)}`;
    const g = groups.get(k);
    if (g) g.push(it); else groups.set(k, [it]);
  }
  const offsets = new Map<number, [number, number]>();
  const hubs: (LatLon & { legs: [number, number][] })[] = [];
  for (const g of groups.values()) {
    if (g.length < 2) continue;
    g.sort((x, y) => x.id - y.id);                       // stable order: newest last
    const r = Math.max(24, (g.length * 34) / (2 * Math.PI)); // 30 px pins, ~4 px apart
    g.forEach((it, i) => {
      const ang = -Math.PI / 2 + (2 * Math.PI * i) / g.length;   // start at 12 o'clock
      offsets.set(it.id, [Math.round(r * Math.cos(ang)), Math.round(r * Math.sin(ang))]);
    });
    hubs.push({ lat: g[0].lat, lon: g[0].lon, legs: g.map((it) => offsets.get(it.id)!) });
  }
  return { offsets, hubs };
}
