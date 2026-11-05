export const DASH = "—";

export function isNum(v: unknown): v is number {
  return typeof v === "number" && Number.isFinite(v);
}

export function fmtNum(v: unknown, digits = 0): string {
  return isNum(v) ? v.toFixed(digits) : DASH;
}

export function fmtDuration(s: number | null | undefined): string {
  if (!isNum(s)) return DASH;
  const t = Math.max(0, Math.floor(s));
  const h = Math.floor(t / 3600), m = Math.floor((t % 3600) / 60), sec = t % 60;
  return [h, m, sec].map((x) => String(x).padStart(2, "0")).join(":");
}

export function fmtCoord(lat: number | null | undefined, lon: number | null | undefined): string {
  return isNum(lat) && isNum(lon) ? `${lat.toFixed(6)}, ${lon.toFixed(6)}` : "no GPS fix";
}

export function fmtClock(epochS: number | null | undefined): string {
  if (!isNum(epochS)) return DASH;
  const d = new Date(epochS * 1000);
  return [d.getHours(), d.getMinutes(), d.getSeconds()].map((x) => String(x).padStart(2, "0")).join(":");
}
