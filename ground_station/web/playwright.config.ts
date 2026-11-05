import { defineConfig, devices } from "@playwright/test";
import os from "node:os";
import path from "node:path";

const PY = process.env.GS_PYTHON ?? "python3";
const REPO = path.resolve(import.meta.dirname, "../..");
export const PORT = 5077;
const DATA = path.join(os.tmpdir(), `gs-e2e-${process.pid}`);

export default defineConfig({
  testDir: "tests/e2e",
  workers: 1,
  timeout: 90_000,
  expect: { timeout: 15_000 },
  reporter: [["list"]],
  use: { baseURL: `http://127.0.0.1:${PORT}`, ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } },
  webServer: {
    command: `"${PY}" ground_station/app.py`,
    cwd: REPO,
    url: `http://127.0.0.1:${PORT}/health`,
    reuseExistingServer: false,
    timeout: 30_000,
    // Hermetic: the station itself has no internet either (all upstream tile/terrain fetches fail),
    // exactly like the field laptop on the DRONE-EDGE hotspot.
    env: { GS_PORT: String(PORT), GS_HOST: "127.0.0.1", GS_DATA_DIR: DATA, GS_BEACON_TARGETS: "127.0.0.1", GS_BEACON_PORT: "5099",
      HTTPS_PROXY: "http://127.0.0.1:9", HTTP_PROXY: "http://127.0.0.1:9", NO_PROXY: "127.0.0.1,localhost" },
  },
});
