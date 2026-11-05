import { test as base, expect, type Page } from "@playwright/test";
import { spawn, type ChildProcess } from "node:child_process";
import os from "node:os";
import path from "node:path";

const PY = process.env.GS_PYTHON ?? "python3";
const REPO = path.resolve(import.meta.dirname, "../../../..");
export const STATION = "http://127.0.0.1:5077";

type Fixtures = { demoDrone: ChildProcess; hosts: Set<string>; consoleGuard: void };

export const test = base.extend<Fixtures>({
  demoDrone: async ({}, use) => {
    const db = path.join(os.tmpdir(), `gs-e2e-drone-${process.pid}-${Date.now()}`, "alerts.db");
    const p = spawn(PY, ["ground_station/demo_drone.py", "--station", STATION, "--cycle", "30", "--db", db],
      { cwd: REPO, stdio: "ignore" });
    await use(p);
    p.kill("SIGINT");
  },
  hosts: async ({ page }, use) => {
    const hosts = new Set<string>();
    page.on("request", (r) => hosts.add(new URL(r.url()).host));
    await use(hosts);
  },
  consoleGuard: [async ({ page }, use) => {
    const errors: string[] = [];
    page.on("console", (m) => {
      if (m.type() !== "error") return;
      // An uncached map/terrain tile 404s offline by design; the browser logs that itself.
      const where = m.location()?.url ?? "";
      if (/Failed to load resource/.test(m.text()) && /\/(tiles|terrain)\//.test(where)) return;
      errors.push(m.text());
    });
    page.on("pageerror", (e) => errors.push(e.message));
    await use();
    expect(errors, "console errors").toEqual([]);
  }, { auto: true }],
});

export { expect };

export async function waitLive(page: Page) {
  await expect(page.getByTestId("link-pill")).toContainText("LIVE", { timeout: 20_000 });
}

export async function mapState(page: Page) {
  return page.evaluate(() => {
    const m = (window as any).__gsMap;
    return m ? { lat: m.getCenter().lat, lng: m.getCenter().lng, pitch: m.getPitch() } : null;
  });
}

let alertSeq = 0;
/** Post an alert straight to the test station (as the drone would). Returns its station id. */
export async function postAlert(request: import("@playwright/test").APIRequestContext,
                                lat: number, lon: number, type = "fire"): Promise<number> {
  alertSeq += 1;
  const key = `e2e-${process.pid}-${Date.now()}-${alertSeq}`;
  await request.post(`${STATION}/alert`, { multipart: {
    alert_id: key, drone_id: "e2e", type, conf: "0.9", lat: String(lat), lon: String(lon), wall_time: key } });
  const st = await (await request.get(`${STATION}/api/state`)).json();
  return Math.max(...st.alerts.map((a: { id: number }) => a.id));
}
