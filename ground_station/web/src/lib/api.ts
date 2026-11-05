import type { Alert, AlertStatus, Mission, StateResponse, Timeline } from "./types";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit & { json?: unknown }): Promise<T> {
  const opts: RequestInit = { ...init };
  if (init?.json !== undefined) {
    opts.method = init.method ?? "POST";
    opts.headers = { "Content-Type": "application/json" };
    opts.body = JSON.stringify(init.json);
  }
  const r = await fetch(path, opts);
  let body: unknown = null;
  try { body = await r.json(); } catch { /* empty or non-JSON body */ }
  if (!r.ok) {
    const msg = (body as { error?: string } | null)?.error ?? `${path} → HTTP ${r.status}`;
    throw new ApiError(r.status, msg);
  }
  return body as T;
}

export const getState = () => request<StateResponse>("/api/state");
export const getMissions = () => request<Mission[]>("/api/missions");
export const getTimeline = (id: number) => request<Timeline>(`/api/missions/${id}/timeline`);

export async function updateAlert(id: number, body: { status?: AlertStatus; note?: string }): Promise<Alert> {
  return (await request<{ alert: Alert }>(`/api/alerts/${id}`, { json: body })).alert;
}

export async function newMission(name?: string): Promise<Mission> {
  return (await request<{ mission: Mission }>("/api/missions", { json: name ? { name } : {} })).mission;
}

export const exportUrl = (id: number, fmt: "csv" | "geojson" | "kml") => `/api/missions/${id}/export.${fmt}`;
export const reportUrl = (id: number) => `/report/${id}`;
export const previewUrl = (t: number) => `/api/preview.jpg?t=${encodeURIComponent(String(t))}`;
export const snapUrl = (name: string) => `/snap/${encodeURIComponent(name)}`;
