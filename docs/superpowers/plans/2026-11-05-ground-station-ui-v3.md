# Ground Station UI v3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the vanilla-JS dashboard with a professional React + TypeScript ground station: Live (3D MapLibre map), Replay timeline, Analytics and Missions views, fully offline, served by the existing Flask station.

**Architecture:**
- The Flask station gains a telemetry history table, a timeline endpoint and a terrain-tile proxy.
- A Vite/React app in `ground_station/web/` builds into `ground_station/static/app/`. That build is committed and served at `/`.
- Live state comes from `/api/state` plus SSE, held in a Zustand store. History comes from TanStack Query on the timeline endpoint.

**Tech Stack:** Python 3 / Flask / SQLite (station). React 19, TypeScript, Vite 8, MapLibre GL 6, ECharts 6, Tailwind 4, Radix UI, cmdk, sonner, lucide-react, Zustand 5, TanStack Query 5, wouter. Tests: pytest, Vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-11-05-ground-station-ui-v3-design.md`

## Global Constraints

- Branch `temp-jetson-fixes` only. **Never push `main`.** Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- The field laptop needs **only Python**. `ground_station/static/app/` (the build output) is committed.
- **No request to any host other than the station** at runtime: no CDN, no Google Fonts, no remote map styles.
- **Exact pinned versions** (`"exact"`, no `^`), all published on or before 2026-10-22:
  - **App:** react 19.3.1 · react-dom 19.3.1 · maplibre-gl 6.15.0 · echarts 6.1.0
  - **Styling:** tailwindcss 4.3.3 · @tailwindcss/vite 4.3.3
  - **Radix:** @radix-ui/react-dialog 1.3.1 · react-dropdown-menu 2.2.1 · react-tooltip 1.4.1 · react-select 2.4.1 · react-slider 1.6.1 · react-toggle-group 1.2.1 · react-tabs 1.2.1
  - **UI helpers:** cmdk 1.1.1 · sonner 2.0.8 · lucide-react 1.61.0 · clsx 2.1.1
  - **State and routing:** zustand 5.0.16 · @tanstack/react-query 5.104.5 · wouter 3.13.0
  - **Fonts:** @fontsource/inter 5.3.0 · @fontsource/jetbrains-mono 5.3.0
  - **Dev:** typescript 7.0.2 · vite 8.3.5 · @vitejs/plugin-react 6.1.2 · @types/react 19.3.0 · @types/react-dom 19.3.0 · vitest 5.0.5 · jsdom 30.1.3 · @testing-library/react 16.3.3 · @testing-library/user-event 14.6.8 · @testing-library/jest-dom 7.0.1 · @playwright/test 1.64.1
- Node ≥ 20.19 (developed on 22.12). TypeScript `strict: true`.
- **Alert colours:** person `#3987e5`, fire `#d95926`, smoke `#199e70`. **Status colours** (state only, always with a label): good `#0ca30c`, warning `#fab219`, serious `#ec835a`, critical `#d03b3b`.
- **Timing and thresholds:**
  - link lost after **3 s** (server clock); preview stale after **5 s**
  - telemetry sampled to the DB at **≥ 5 s** per drone
  - analytics refetch every **30 s** for the live mission
  - clustering above **25** alerts; 3D pitch **60°**
  - replay speeds **1× / 4× / 16×**, step **10 s**
  - temperature warning **≥ 70 °C**, critical **≥ 80 °C**
- **Terrain:**
  - source `https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png`, zoom 0–15, Terrarium encoding
  - attribution `© OpenStreetMap contributors · Terrain: Mapzen, AWS Terrain Tiles`
- **Sounds:** person two-tone 880 → 660 Hz; fire and smoke 520 Hz.
- **Performance:** the first-load JS (shell + Live) is ≤ 700 KB gzip. Replay and Analytics are lazy chunks.
- **Commands:**
  - Python tests: `$PY -m pytest -q -p no:cacheprovider` from the repo root (`$PY` = the scratchpad venv Python)
  - JS commands run from `ground_station/web/`: `npm test` (Vitest), `npm run test:e2e` (Playwright), `npm run build`, `npm run typecheck`

## Review Focus

1. **A mission with no telemetry or track** (just created, or a v2-era mission before `telemetry_log` existed). Replay and Analytics should show calm empty states, not crash or draw NaN charts. → tests in Tasks 9 and 10.
2. **v2 alerts with `received_at = NULL`.** Replay should still show them, pinned to the mission start, and Analytics should still count them. → tests in Tasks 9 and 10.
3. **The browser clock is hours off from the station.** The mission timer, link age and preview age should still be right. → test in Task 5.
4. **The station restarts or becomes unreachable while the UI is open.** The UI should show "Reconnecting…", then recover and resync without a reload, and toast alerts missed in the gap. → tests in Task 5 (unit) and Task 11 (e2e).
5. **A long mission** (10 000 telemetry samples, 1 000 alerts). The analytics maths should stay fast (< 50 ms) and the alert list usable. → tests in Task 10 (and the list size in Task 8).

---

## Shared TypeScript types (`ground_station/web/src/lib/types.ts`, created in Task 5)

```ts
export type AlertType = "person" | "fire" | "smoke";
export type AlertStatus = "new" | "acknowledged" | "resolved";
export interface Alert { id: number; mission_id: number; drone_id: string | null; type: AlertType; conf: number;
  lat: number | null; lon: number | null; wall_time: string | null; received: string | null;
  received_at: number | null; snapshot: string | null; status: AlertStatus; note: string | null;
  acked_at: string | null; resolved_at: string | null; }
export interface Mission { id: number; name: string; started_at: string; ended_at: string | null;
  started_ts: number; ended_ts: number | null; }
export interface Gps { mode?: string; fix?: boolean | null; lat?: number | null; lon?: number | null; alt_m?: number | null;
  sats?: number | null; hdop?: number | null; speed_mps?: number | null; course_deg?: number | null; age_s?: number | null; }
export interface Pipeline { state?: "idle" | "scanning" | "active"; fps?: number | null; frames?: number; stage1_ms?: number | null;
  stage2_ms?: number | null; stage2_runs?: number; stage2_skipped?: number; triggers?: number;
  last_detection?: { type: AlertType; conf: number; t: number } | null; }
export interface SystemStats { power_mw?: number | null; cpu_temp_c?: number | null; gpu_temp_c?: number | null;
  cpu_load_pct?: number | null; gpu_load_pct?: number | null; ram_used_mb?: number | null; ram_total_mb?: number | null; }
export interface Telemetry { drone_id?: string | null; seq?: number; time?: number; uptime_s?: number; gps?: Gps | null;
  pipeline?: Pipeline | null; system?: SystemStats | null; link?: { alerts_buffered?: number; alerts_sent?: number } | null; }
export interface TrackPoint { t: number; lat: number; lon: number; alt_m: number | null; }
export interface TelemetrySample { t: number; lat: number | null; lon: number | null; alt_m: number | null;
  speed_mps: number | null; course_deg: number | null; sats: number | null; fix: number | null; fps: number | null;
  state: string | null; stage2_runs: number | null; stage2_skipped: number | null; power_mw: number | null;
  cpu_temp_c: number | null; gpu_temp_c: number | null; cpu_load_pct: number | null; gpu_load_pct: number | null; }
export interface LinkInfo { state: "live" | "lost" | "never"; age_s: number | null; }
export interface Preview { t: number; frame_t?: number | null; stage2: boolean; }
export interface StateResponse { server_time: number; mission: Mission; missions: Mission[]; link: LinkInfo;
  telemetry: Telemetry | null; preview: Preview | null; alerts: Alert[]; track: TrackPoint[]; }
export interface Timeline { mission: Mission; server_time: number; track: TrackPoint[];
  telemetry: TelemetrySample[]; alerts: Alert[]; }
```

---

### Task 1: Store, the telemetry log, mission timestamps, alert reopen

**Files:**
- Modify: `ground_station/store.py`
- Test: `tests/test_gs_store.py`

**Interfaces:**
- Produces:
  - **missions:** mission dicts gain `started_ts`, `ended_ts` (floats, unix seconds)
  - **alerts:**
    - alert dicts gain `received_at` (float or None); `add_alert` sets it to `time.time()`
    - `ALERT_COLS` gains `"received_at"`
    - `update_alert(aid, status="new"|"acknowledged")` sets `resolved_at = NULL`
  - **telemetry log:**
    - `Store.add_telemetry_sample(drone_id: str, t: float, telemetry: dict) -> bool`: stores one row if ≥ 5 s have passed since that drone's last stored row. Non-finite or non-numeric values become NULL. Returns whether it wrote.
    - `Store.telemetry_log(mission_id: int) -> list[dict]`: the `TelemetrySample` keys from the shared types, ordered by `t`
    - `TELEMETRY_SAMPLE_S = 5.0`

- [ ] **Step 1: Write the failing tests**
  - `test_mission_has_epoch_times`: `started_ts` is within 2 s of `time.time()`, and `ended_ts is None`. After `new_mission()` the old mission has `ended_ts >= started_ts`.
  - `test_alert_received_at_set`
  - `test_reopen_clears_resolved_at`: resolve, then `update_alert(id, status="acknowledged")` → `resolved_at is None` and `acked_at` is kept.
  - `test_telemetry_sample_throttle`:
    - samples at t = 100, 102, 105.5, 106 → only 100 and 105.5 are stored
    - fields mapped from a v2-shaped telemetry dict: `gps.lat` → `lat`, `pipeline.fps` → `fps`, `system.power_mw` → `power_mw`, `gps.fix` True → `fix == 1`
  - `test_telemetry_sample_nonfinite_to_null`: `gps.lat = float("nan")` and `system.power_mw = "x"` → stored as None, and the row still exists.
  - `test_migrates_v2_station_db(tmp_path)`:
    - build the v2 schema by hand (the `missions`, `alerts` with the workflow columns, and `track` DDL from `store.py` at commit 9000ed8) with one mission whose `started_at` is `'2026-11-05 10:00:00'` and one alert
    - after opening it: `received_at is None` for the old alert, `started_ts == time.mktime(time.strptime('2026-11-05 10:00:00', '%Y-%m-%d %H:%M:%S'))`, `telemetry_log(1) == []`
- [ ] **Step 2: Run them, expect FAIL** (KeyError / AttributeError).
- [ ] **Step 3: Implement**
  - ALTER-add the new columns, as the v2 migration does.
  - Backfill `started_ts` / `ended_ts` from the text columns with `time.mktime(time.strptime(...))`.
  - `CREATE TABLE IF NOT EXISTS telemetry_log (…)` with the spec §4.1 columns, plus `CREATE INDEX IF NOT EXISTS tl_mission ON telemetry_log(mission_id, t)`.
  - Keep the last-sample time per drone in memory (like `_last_track`), cleared by `new_mission`.
- [ ] **Step 4: Run them, expect PASS. Then run the full pytest suite, expect PASS.**
- [ ] **Step 5: Commit** `feat(gs): telemetry log, mission epochs, alert received_at, reopen clears resolved_at`

---

### Task 2: Station API, timeline, and serving the built UI

**Files:**
- Modify: `ground_station/app.py`
- Test: `tests/test_gs_api.py`

**Interfaces:**
- Consumes: Task 1 (`add_telemetry_sample`, `telemetry_log`, epoch fields).
- Produces:
  - `POST /api/telemetry` also calls `store.add_telemetry_sample(drone_id, received_at, body)`.
  - `GET /api/missions/<int:mid>/timeline` → `Timeline` JSON. Unknown id → 404.
  - `GET /api/missions` items gain `alert_counts: {person, fire, smoke}` (totals) and `distance_m` (track length, same formula as `exports._dist_m`). Add both as optional fields on the TS `Mission` type.
  - `POST /api/alerts/<id>` and `POST /api/missions`: a body that is present but not a JSON object → 400.
  - `GET /`:
    - serves `BASE/static/app/index.html` with `Cache-Control: no-cache`
    - if the build is missing → 503, with the text `Dashboard not built. Run: cd ground_station/web && npm ci && npm run build`
  - `create_app(..., ui_dir=None)`: injectable for tests (defaults to `BASE/static/app`).

- [ ] **Step 1: Write the failing tests**
  - `test_timeline_shape`: post 2 telemetry bodies (monkeypatch `store.TELEMETRY_SAMPLE_S = 0`) and 1 alert. Then `/api/missions/1/timeline`:
    - has keys `mission, server_time, track, telemetry, alerts`
    - `len(telemetry) == 2`, and `alerts[0]["received_at"]` is a float
  - `test_timeline_unknown_404`
  - `test_state_missions_have_epochs`: `st["mission"]["started_ts"]` is a float.
  - `test_missions_list_counts_and_distance`: 2 fire + 1 person alerts, plus 2 track points 0.001° apart (via telemetry with `fix: true`) → `alert_counts == {"person": 1, "fire": 2, "smoke": 0}` and `distance_m ≈ 111.32`.
  - `test_non_object_json_400`: `[1]` and `"x"` to `/api/alerts/1` and to `/api/missions` → 400.
  - `test_index_serves_built_ui(tmp_path)`:
    - write `tmp_path/ui/index.html` containing `<div id="root">`, then `create_app(..., ui_dir=str(tmp_path/"ui"))`
    - `GET /` → 200, contains `id="root"`, and `Cache-Control` is `no-cache`
  - `test_index_without_build_503`
  - Replace the existing `test_dashboard_has_no_external_assets` with the same assertion against a fake built `index.html` that references `/static/app/assets/x.js`. The real check moves to Playwright in Task 11.
- [ ] **Step 2: Run them, expect FAIL**
- [ ] **Step 3: Implement**
  - Stop rendering `templates/index.html` (the file is deleted in Task 11).
  - The 503 body is plain text.
- [ ] **Step 4: Run them, expect PASS. Then the full suite.**
- [ ] **Step 5: Commit** `feat(gs): mission timeline API, telemetry history, serve built UI`

---

### Task 3: Terrain tile proxy and terrain prefetch

**Files:**
- Modify: `ground_station/tiles.py`, `ground_station/app.py`
- Test: `tests/test_gs_exports_tiles.py`

**Interfaces:**
- Produces:
  - `tiles_blueprint(cache_dir, fetch=None, *, name="tiles", url_prefix="/tiles", max_zoom=19)`, generalised
  - `terrain_fetch(z, x, y) -> bytes | None` using `TERRAIN_URL`
  - `create_app(..., terrain_fetch=None)` registers a second blueprint with `name="terrain"`, `url_prefix="/terrain"`, `max_zoom=15`, cache `<data_dir>/terrain`
  - The CLI gains `--terrain`: also prefetches the terrain tiles for the bbox at `min(zmax, 15)`. The total (map + terrain) is capped at `MAX_PREFETCH`.
  - Each blueprint has its own offline backoff.

- [ ] **Step 1: Write the failing tests**
  - `test_terrain_cached_fetched_once`: through `create_app(..., terrain_fetch=fake)`, `/terrain/3/2/1.png` twice → fake called once, 200 `image/png`.
  - `test_terrain_zoom_limit_404`: `/terrain/16/1/1.png` → 404.
  - `test_terrain_offline_backoff_independent`: a terrain failure doesn't block `/tiles` fetches.
  - `test_prefetch_terrain_counts(capsys)`: `--dry-run --terrain --zoom 14-17` → exit code 0, and the printed count is larger than without `--terrain`.
- [ ] **Step 2: Run them, expect FAIL**
- [ ] **Step 3: Implement** (blueprint names must be unique, so pass `name`).
- [ ] **Step 4: Run them, expect PASS. Then the full suite.**
- [ ] **Step 5: Commit** `feat(gs): cached AWS terrain tile proxy and terrain prefetch`

---

### Task 4: Frontend scaffold, design tokens, and pure libraries

**Files:**
- Create `ground_station/web/`:
  - `package.json`, `vite.config.ts`, `tsconfig.json`, `index.html`, `playwright.config.ts`, `.gitignore` (`node_modules`, `test-results`, `playwright-report`)
  - `src/main.tsx`, `src/App.tsx` (a placeholder shell that renders the "Ground Station" heading)
  - `src/styles/tokens.css`, `src/styles/index.css`
  - `src/lib/{clock.ts,format.ts,geo.ts,prefs.ts}`
  - `tests/unit/{clock,format,geo,prefs}.test.ts`, `tests/setup.ts`
- Create: `ground_station/static/app/` (build output)
- Modify: the root `.gitignore` (add `ground_station/web/node_modules/`)

**Interfaces:**
- Produces:
  - **`clock.ts`:** `createClock(): { sync(serverTimeS: number, localMs?: number): void; now(): number }`. `now()` returns server seconds.
  - **`format.ts`:**
    - `fmtNum(v: unknown, digits = 0): string` → `"—"` unless it's a finite number
    - `fmtDuration(s: number | null): string` → `"HH:MM:SS"`, or `"—"`
    - `fmtCoord(lat, lon): string` → 6 decimals, or `"no GPS fix"`
    - `fmtClock(epochS: number): string` → local `HH:MM:SS`
  - **`geo.ts`:**
    - `distanceM(a: {lat; lon}, b: {lat; lon}): number`, using the same equirectangular 111 320 m formula as the backend
    - `pathDistanceM(pts): number`
    - `lerpAngle(a: number, b: number, f: number): number`, taking the shortest way around 360°
    - `interpolateAt(samples: {t; lat; lon; course_deg?}[], t: number): {lat; lon; course: number | null} | null`. It skips samples with null lat/lon, clamps outside the range, and returns null if there are no valid samples.
  - **`prefs.ts`:** `loadPrefs(): Prefs; savePrefs(p: Prefs): void`, with `try/catch` around `localStorage`. The default is `{theme: "system", mute: false, follow: true, map3d: false, headingUp: false, types: ["person","fire","smoke"], status: "open"}`.
  - **`vite.config.ts`:**
    - `base: "/static/app/"`, `build.outDir: "../static/app"`, `emptyOutDir: true`
    - `server.proxy` for `/api`, `/alert`, `/snap`, `/tiles`, `/terrain`, `/report`, `/health` → `http://127.0.0.1:5000`
    - plugins `react()` and `tailwindcss()`
    - `manualChunks`: `maplibre` and `echarts` get their own chunks
  - **`package.json` scripts:**
    - `dev`
    - `build` (`tsc -b && vite build`)
    - `typecheck` (`tsc -b --noEmit`)
    - `test` (`vitest run`)
    - `test:e2e` (`playwright test`)
    - `check:build` (`node scripts/check-build.mjs`, added in Task 11)
  - **`tokens.css`:**
    - `:root` holds the light tokens. `[data-theme="dark"]`, plus `@media (prefers-color-scheme: dark)` under `:root:not([data-theme="light"])`, hold the dark tokens.
    - dark tokens: bg `#0d1016`, surface `#141821`, surface-2 `#1b202b`, surface-3 `#232a37`, line `#2a3140`, text `#e8ebf1`, text-2 `#a9b0bd`, muted `#7a8293`
    - light surface `#f6f7f9`
    - alert and status colours as in Global Constraints. The light-theme alert colours must pass `validate_palette.js --mode light` against the light surface (run it and record the result in the commit message).

- [ ] **Step 1: Scaffold.** `npm init`-equivalent `package.json` with the exact versions from Global Constraints, then `npm install`. Configure Vitest (`environment: "jsdom"`, `setupFiles: ["tests/setup.ts"]`, which imports `@testing-library/jest-dom/vitest`).
- [ ] **Step 2: Write the failing unit tests**
  - **`clock.test.ts`:** `sync(1000, 0)` then advance local time 5000 ms (fake timers or an injected `localMs`) → `now()` is about 1005. A browser clock 3 h off doesn't change `now()` (Review Focus 3).
  - **`format.test.ts`:**
    - `fmtNum(null) === "—"`, `fmtNum(NaN) === "—"`, `fmtNum(2.345, 1) === "2.3"`
    - `fmtDuration(3725) === "01:02:05"`
    - `fmtCoord(null, 1) === "no GPS fix"`
  - **`geo.test.ts`:**
    - `distanceM` for 0.001° of latitude ≈ 111.32 m (within 0.1 %)
    - `lerpAngle(350, 10, 0.5) === 0`, and `lerpAngle(10, 350, 0.25) === 5`
    - `interpolateAt` halfway between two samples → the midpoint
    - before the first sample → the first sample; empty → null
    - samples with null lat are skipped
  - **`prefs.test.ts`:** defaults come back when `localStorage.getItem` throws, and a save then load round-trips.
- [ ] **Step 3: Run `npm test`, expect FAIL** (modules missing).
- [ ] **Step 4: Implement the four libraries, the tokens, and the placeholder `App.tsx`.**
  - Import fonts in `main.tsx`: `@fontsource/inter/400.css`, `500.css`, `600.css`, `700.css`, and `@fontsource/jetbrains-mono/500.css`.
- [ ] **Step 5: Run `npm test` and `npm run typecheck`, expect PASS. Then `npm run build`:** `ground_station/static/app/index.html` exists, and its asset URLs start with `/static/app/`.
- [ ] **Step 6: Commit** `feat(ui): React/TS/Vite scaffold, design tokens, core libs` (including `package-lock.json` and `static/app/`).

---

### Task 5: API client, live store, and SSE connection

**Files:**
- Create: `src/lib/types.ts` (the shared types above), `src/lib/api.ts`, `src/lib/sse.ts`, `src/store/live.ts`
- Test: `tests/unit/api.test.ts`, `tests/unit/live-store.test.ts`, `tests/unit/sse.test.ts`

**Interfaces:**
- **`api.ts`:**
  - `getState(): Promise<StateResponse>`
  - `getMissions(): Promise<Mission[]>`
  - `getTimeline(id: number): Promise<Timeline>`
  - `updateAlert(id: number, body: {status?: AlertStatus; note?: string}): Promise<Alert>`
  - `newMission(name?: string): Promise<Mission>`
  - `exportUrl(id, fmt: "csv"|"geojson"|"kml"): string`, `reportUrl(id): string`, `previewUrl(t: number): string`, `snapUrl(name: string): string` (with `encodeURIComponent`)
  - A non-2xx response throws `ApiError {status, message}`.
- **`store/live.ts`:** `useLive` (Zustand).
  - **State:** `{clock, mission, missions, telemetry, telemetryAt: number|null, preview: Preview|null, alerts: Record<number, Alert>, track: TrackPoint[], seen: Set<number>, loaded: boolean, connection: "connecting"|"open"|"reconnecting"}`
  - **Actions:**
    - `hydrate(s: StateResponse): Alert[]`. Returns the missed alerts: after the first hydrate, alerts that are `new` and were not in `seen`.
    - `applyEvent(name: string, data: any): {notify?: Alert}`:
      - `telemetry` → set `telemetry` and `telemetryAt = data.server_time`, and append a track point if there's a finite fix
      - `alert` → ignored if `mission_id` ≠ the current mission; otherwise insert it and return `notify` if unseen
      - `alert_update` → replace the alert if known
      - `preview` → set `preview`
      - `mission` → `connection` is unchanged, and the caller re-hydrates
      - `link` → only syncs the clock
    - `setConnection(c)`
  - **Selectors:**
    - `linkState(s, nowS): LinkInfo`, with a 3 s threshold
    - `visibleAlerts(s, prefs): Alert[]`, sorted (resolved last, then priority person < fire < smoke, then newest)
- **`sse.ts`:** `connect(opts: {onEvent(name, data), onOpen(), onState(c)}): () => void`.
  - It wraps `EventSource('/api/stream')`, registers the 7 event names, and calls `onOpen` on every `open`.
  - On `error` it calls `onState("reconnecting")`.
  - The returned function closes it.

- [ ] **Step 1: Write the failing tests**
  - **`live-store.test.ts`:**
    - `hydrate` on the first call returns `[]` and marks everything seen
    - a second `hydrate` containing a new unseen `new` alert returns it (Review Focus 4)
    - an `alert` event for another mission is ignored
    - an `alert` event for the current mission returns `notify`; the same event again returns no `notify`
    - a `telemetry` event with `gps.lat = null` doesn't append a track point
    - `linkState` is `"live"` at age 2.9 s and `"lost"` at age 3.1 s, when the browser clock is 3 h off from the server (Review Focus 3)
    - `visibleAlerts` ordering and filters
  - **`api.test.ts`** (mocked `fetch`):
    - `updateAlert` POSTs JSON to `/api/alerts/7`
    - a 400 response throws `ApiError` with status 400
    - `snapUrl("a b.jpg") === "/snap/a%20b.jpg"`
  - **`sse.test.ts`** (fake EventSource class on `globalThis`): `open` calls `onOpen` and `onState("open")`; `error` calls `onState("reconnecting")`; a named event is parsed and passed to `onEvent`.
- [ ] **Step 2: Run them, expect FAIL**
- [ ] **Step 3: Implement**
- [ ] **Step 4: `npm test` and `npm run typecheck`, expect PASS**
- [ ] **Step 5: Commit** `feat(ui): typed API client, live store, SSE connection`

---

### Task 6: App shell, theme, notifications, command palette, shortcuts

**Files:**
- Create:
  - `src/ui/{Button,Badge,Card,Kbd,Dialog,Sheet,Tooltip,DropdownMenu,Select,ToggleGroup,Slider}.tsx` (thin Radix/Tailwind wrappers)
  - `src/features/shell/{AppShell,CommandBar,NavRail,CommandPalette,Notifier,PersonBanner,ErrorBoundary,ShortcutHelp}.tsx`
  - `src/hooks/{useShortcuts,useServerNow,useTheme}.ts`
  - `src/routes.tsx`
- Modify: `src/App.tsx`
- Test: `tests/unit/shortcuts.test.tsx`, `tests/unit/notifier.test.tsx`, `tests/unit/shell.test.tsx`

**Interfaces:**
- Consumes: Task 5 store, api and sse; Task 4 prefs and format.
- Produces:
  - **Routes** (wouter `useHashLocation`): `/live` (default), `/replay/:id?`, `/analytics/:id?`, `/missions`. Replay and Analytics are `React.lazy`.
  - **`useShortcuts(map: Record<string, () => void>)`:** ignores events from `input`, `textarea`, `select` or `[contenteditable]`, and when Ctrl/Cmd/Alt is held, except for `mod+k`.
  - **Keys:** `a`, `r`, `f`, `3`, `n`, `space`, `arrowleft`, `arrowright`, `?`, `mod+k`.
  - **Selected-alert context:** `useSelection()`, i.e. `{selectedId, select(id|null)}` (Zustand slice in `store/ui.ts`). It's used by the shortcuts, the map and the drawer.
  - **`Notifier`:** subscribes to the store's `notify` results (`useLive.subscribe`). For each alert it shows a sonner toast and plays the tone (unless muted), updates `document.title` to `(N) New alerts · Ground Station` (N = count of `new`), and writes to an `aria-live="assertive"` region. Person alerts that are still `new` keep the `PersonBanner` visible.
  - **`ErrorBoundary`:** a per-panel fallback card with "This panel failed" and a "Reload panel" button that resets the boundary.
  - **`CommandBar`:**
    - mission name and timer (`fmtDuration(serverNow - mission.started_ts)`)
    - link pill (`LIVE · <drone_id>` / `LINK LOST · N s` / `WAITING FOR DRONE`, plus `Reconnecting…` when `connection === "reconnecting"`)
    - GPS chip (`FIX · N sats · HDOP x`, `NO FIX`, `SIM GPS`)
    - counters, mute, the ⌘K button, the Export menu, New mission (a Dialog asking for a name)
  - **`NavRail`:** left rail at ≥ 768 px; bottom tab bar below that.
  - **Boot** (`App.tsx`), applying events directly (telemetry is 1 Hz; React 19 batches automatically): QueryClientProvider, then `getState()` → `hydrate`, then `connect()` (`onOpen` → re-hydrate + notify the missed alerts; `onEvent` → `applyEvent`), plus the theme.

- [ ] **Step 1: Write the failing tests**
  - **`shortcuts.test.tsx`:** pressing `a` on the body calls the handler; pressing `a` while focused in an `<input>` doesn't; `mod+k` works even from the input.
  - **`notifier.test.tsx`:** with an AudioContext mock and the store fed a `notify` for a person alert:
    - a toast with the text `New person alert` appears
    - `document.title` starts `(1) New alerts`
    - the banner is visible, and disappears once the alert's status becomes `acknowledged`
    - when muted, no oscillator is started
  - **`shell.test.tsx`** (store hydrated with fixtures): the link pill text is `LIVE · nano`; navigating to `#/missions` renders the Missions route; an ErrorBoundary around a throwing child shows `This panel failed`.
- [ ] **Step 2: Run them, expect FAIL**
- [ ] **Step 3: Implement.** The command palette uses `cmdk` with these groups:
  - **Go to:** Live, Replay, Analytics, Missions
  - **Mission:** New mission, Export CSV, GeoJSON, KML, Report
  - **View:** toggle 3D, follow, north-up, theme, mute
  - **Alerts:** the 20 most recent, which select the alert and fly to it
- [ ] **Step 4: `npm test` and `npm run typecheck`, expect PASS. Then `npm run build`.**
- [ ] **Step 5: Commit** `feat(ui): app shell, command bar, palette, notifications, shortcuts`

---

### Task 7: The mission map (MapLibre)

**Files:**
- Create: `src/features/map/{MissionMap.tsx,mapStyle.ts,droneLayer.ts,alertLayer.ts,MapControls.tsx,webgl.ts,useAnimatedDrone.ts}`
- Test: `tests/unit/map-style.test.ts`, `tests/unit/animated-drone.test.ts`, `tests/unit/map-fallback.test.tsx`

**Interfaces:**
- Consumes: geo (Task 4), store and selection (Tasks 5 and 6), prefs.
- Produces:
  - **`buildStyle({dark: boolean}): StyleSpecification`:**
    - raster source `osm` (`tiles: ["/tiles/{z}/{x}/{y}.png"]`, `tileSize: 256`, `maxzoom: 19`)
    - raster-dem source `terrain` (`tiles: ["/terrain/{z}/{x}/{y}.png"]`, `encoding: "terrarium"`, `maxzoom: 15`, `tileSize: 256`)
    - a background layer (the grid colour from the tokens), then the `osm` raster layer (`raster-brightness-max` 0.75 in dark mode)
    - **no `glyphs` or `sprite` URLs**: alert letters and the drone are HTML markers, so the style needs no font server
  - **`hasWebGL(): boolean`**
  - **`<MissionMap mode="live"|"replay" drone={{lat, lon, course}|null} trail={[lon, lat][]} alerts={Alert[]} onSelectAlert={(id) => void} />`:**
    - **drone:** a rotated SVG `maplibregl.Marker`, smoothed by `useAnimatedDrone` in live mode
    - **trail:** a GeoJSON line layer with `line-gradient` (needs `lineMetrics: true`)
    - **alerts:**
      - a GeoJSON source with `cluster: true`, `clusterMaxZoom: 17`, `clusterRadius: 40`, active when there are more than 25 alerts (otherwise plain HTML markers)
      - clusters are shown as HTML markers with per-type counts, using `clusterProperties` sums for person, fire and smoke
      - unclustered points are HTML markers with the P/F/S letter, a `new` pulse class, `resolved` dimmed and `selected` outlined
  - **Test hook:** when `location.search` contains `debug=1`, `MissionMap` assigns its map instance to `window.__gsMap` (used by Playwright).
  - **`MapControls`:** zoom, compass and north-up, 2D/3D, heading-up, follow, fit-all, and the layers popover (trail, alerts, terrain, dim basemap).
    - **3D** = `easeTo({pitch: 60})` + `setTerrain({source: "terrain", exaggeration: 1.3})`.
    - If the `terrain` source reports tile errors for 3 s after enabling, terrain is turned off, the map stays tilted, and a hint shows: `Terrain not cached for this area`.
  - **`useAnimatedDrone(target: {lat, lon, course} | null, durationMs = 1000)`:** returns the current `{lat, lon, course}` on each animation frame, interpolating from the last value to the target (`lerpAngle` for course).

- [ ] **Step 1: Write the failing tests**
  - **`map-style.test.ts`:** the `buildStyle` sources match the values above. `JSON.stringify(style)` contains no `http` (Global Constraint: no other host) and no `glyphs` or `sprite` keys.
  - **`animated-drone.test.ts`** (fake `requestAnimationFrame` and `performance.now`): moving from A to B over 1000 ms gives the midpoint at 500 ms. Course 350 → 10 passes through 0, not 180.
  - **`map-fallback.test.tsx`:** with `hasWebGL` mocked to `false`, `<MissionMap>` renders the text `Map needs WebGL` and does not construct `maplibregl.Map` (module mock asserts it isn't called).
- [ ] **Step 2: Run them, expect FAIL**
- [ ] **Step 3: Implement.** MapLibre is imported only in `features/map/*`, so it stays in its own chunk. Add the attribution control with the exact string from Global Constraints.
- [ ] **Step 4: `npm test` and `npm run typecheck`, expect PASS**
- [ ] **Step 5: Commit** `feat(ui): MapLibre mission map with 3D terrain, smooth drone, clustering`

---

### Task 8: Live view: camera, flight readout, alert drawer

**Files:**
- Create: `src/features/live/{LiveView.tsx,CameraCard.tsx,FlightHud.tsx,Compass.tsx,Gauge.tsx,Sparkline.tsx}`, `src/features/alerts/{AlertDrawer.tsx,AlertList.tsx,AlertRow.tsx,AlertDetail.tsx,AlertFilters.tsx}`
- Test: `tests/unit/alerts.test.tsx`, `tests/unit/live.test.tsx`

**Interfaces:**
- Consumes: the store, api, selection, prefs, `MissionMap`, `useServerNow`.
- Produces:
  - **`LiveView`:** a full-bleed `MissionMap mode="live"` with floating `CameraCard` and `FlightHud` panels (left) and the `AlertDrawer` (right). Below 768 px these become bottom Sheets, opened from buttons. Each panel is wrapped in `ErrorBoundary`.
  - **`CameraCard`:**
    - `<img src={previewUrl(preview.t)}>` swapped only once the new image has loaded
    - an age label (`live` under 1.5 s, otherwise `N s ago`)
    - a `YOLO ACTIVE` badge when `preview.stage2`; a `STALE` overlay when the age is ≥ 5 s
    - full screen through a Dialog
  - **`FlightHud`:**
    - `Compass` (`course_deg`), speed, altitude, satellites and HDOP
    - pipeline state with a dot, frame rate, Stage 1 / Stage 2 ms, YOLO runs and skipped
    - `Gauge` for power (0–10 W)
    - CPU and GPU temperature with **text labels** `WARM` (≥ 70) and `HOT` (≥ 80)
    - loads, RAM, alerts waiting
    - 60 s `Sparkline` (canvas) for frame rate and power, with a hover readout `value · N s ago`
  - **`AlertDrawer`:**
    - `AlertFilters` (a ToggleGroup for types, a Select for status, both saved in prefs)
    - `AlertList` (memoised `AlertRow`s; above 200 visible rows it renders the first 200 plus a "Show more" button)
    - `AlertDetail` (a Sheet):
      - zoomable snapshot (click to toggle 2×), type, confidence, `fmtCoord`, Copy, Fly to
      - received time (`fmtClock(received_at)`), acked and resolved times
      - note textarea (Save), and the Acknowledge / Resolve / Reopen buttons calling `updateAlert`
      - on an API error: an `Update failed` toast, with the status unchanged

- [ ] **Step 1: Write the failing tests**
  - **`alerts.test.tsx`:**
    - clicking Acknowledge calls `updateAlert(id, {status: "acknowledged"})`
    - Reopen on a resolved alert sends `{status: "acknowledged"}`
    - an API rejection shows `Update failed`, and the row keeps its old status
    - an alert without lat/lon shows `no GPS fix` and no Fly-to button
    - 500 alerts → 200 rows plus `Show more` (Review Focus 5)
  - **`live.test.tsx`** (store fixtures):
    - telemetry with `system.cpu_temp_c = 82` shows `HOT`
    - `gps` null shows `—` for speed and doesn't crash (spec §6)
    - a preview aged 6 s (server clock) shows `STALE`
- [ ] **Step 2: Run them, expect FAIL**
- [ ] **Step 3: Implement**
- [ ] **Step 4: `npm test` and `npm run typecheck`, expect PASS. Then `npm run build`.**
- [ ] **Step 5: Commit** `feat(ui): live view with camera, flight readout and alert workflow`

---

### Task 9: Replay view

**Files:**
- Create: `src/features/replay/{replay.ts,ReplayView.tsx,Timeline.tsx,ReplaySidePanel.tsx}`
- Test: `tests/unit/replay.test.ts`, `tests/unit/replay-view.test.tsx`

**Interfaces:**
- Consumes: `getTimeline` (TanStack Query key `["timeline", id]`; `refetchInterval` 30 000 ms when the mission has no `ended_ts`), geo, `MissionMap mode="replay"`.
- Produces (`replay.ts`):
  - `bounds(tl: Timeline): {start: number; end: number}`
    - start = `mission.started_ts`
    - end = `max(last telemetry t, last track t, last alert received_at, mission.ended_ts ?? start)`
  - `alertTime(a: Alert, tl: Timeline): number`: `received_at`, or `mission.started_ts` when it's null (Review Focus 2)
  - `alertsAt(tl, t): Alert[]`: alerts with `alertTime ≤ t`
  - `stateAt(tl, t): {drone: {lat; lon; course} | null; sample: TelemetrySample | null; trail: [number, number][]}`:
    - the drone comes from `interpolateAt` over the telemetry samples, falling back to the track points
    - `sample` is the nearest sample at or before *t*
    - `trail` is the track up to *t* as `[lon, lat]`
  - **Playback reducer:**
    - state `{t, playing, speed: 1|4|16}`
    - actions `play`, `pause`, `toggle`, `seek(t)`, `step(±10)`, `setSpeed`, `tick(dtMs)`
    - `tick` advances `t += dtMs/1000*speed` and pauses at the end
- **`ReplayView`:**
  - mission Select (defaults to the route id, or the latest mission)
  - the map at *t*
  - `Timeline`: a range slider, time labels (`fmtDuration(t - start)`), alert ticks (positioned by `alertTime`, coloured by type, clicking calls `seek`), and a pipeline-state band drawn from `sample.state` segments
  - Play/Pause, a speed ToggleGroup, ±10 s buttons, Space and ←/→ shortcuts
  - `ReplaySidePanel`: the sample values at *t*, plus the snapshot of the latest alert ≤ *t*
  - for a mission without `ended_ts`, a "Jump to live" button
  - **empty state:** with no telemetry and no track, show `No flight data recorded for this mission` and the alert list only (Review Focus 1)

- [ ] **Step 1: Write the failing tests**
  - **`replay.test.ts`:**
    - with fixtures, `alertsAt(start - 1)` is empty and `alertsAt(end)` contains all of them
    - an alert with `received_at: null` is visible at `start` (Review Focus 2)
    - `stateAt` halfway between two samples gives the midpoint drone, and the trail only includes points ≤ *t*
    - `bounds` of an empty timeline is `{start: started_ts, end: started_ts}`
    - `tick` at speed 16 for 1000 ms advances 16 s; it clamps at the end and sets `playing = false`
    - `step(-10)` at start stays at start
  - **`replay-view.test.tsx`** (Query client with fixture data; MissionMap mocked):
    - clicking an alert tick moves the slider value to that alert's time
    - an empty timeline shows `No flight data recorded for this mission`
- [ ] **Step 2: Run them, expect FAIL**
- [ ] **Step 3: Implement.** The `tick` driver is `requestAnimationFrame` while `playing`.
- [ ] **Step 4: `npm test` and `npm run typecheck`, expect PASS**
- [ ] **Step 5: Commit** `feat(ui): mission replay timeline`

---

### Task 10: Analytics and Missions views

**Files:**
- Create: `src/features/analytics/{metrics.ts,AnalyticsView.tsx,KpiTile.tsx,charts.tsx,echarts.ts,TelemetryTable.tsx}`, `src/features/missions/MissionsView.tsx`
- Test: `tests/unit/metrics.test.ts`, `tests/unit/analytics-view.test.tsx`, `tests/unit/missions.test.tsx`

**Interfaces:**
- Consumes: `getTimeline`, `getMissions`, `alertTime` and `bounds` (Task 9), `pathDistanceM`.
- Produces:
  - **`metrics.ts`:**
    - `detectionsPerMinute(tl): {minute: number; person: number; fire: number; smoke: number}[]`
      - buckets are 60 s from `bounds.start`, with zero-filled buckets up to `bounds.end`
      - alerts are placed by `alertTime`
    - `summary(tl)`, returning:
      - `durationS`, `distanceM` (track), `counts` (`{[type]: {total, open}}`; open = not resolved)
      - `stage2Runs`, `stage2Skipped`, `computeSavedPct`:
        - runs and skipped are taken from the last sample that has them
        - saved % = `skipped / (runs + skipped) * 100`, or null when both are 0
      - `avgPowerW`, `peakPowerW`, `peakCpuC`, `peakGpuC` (null when there's no data)
  - **`echarts.ts`:** registers only `LineChart`, `BarChart`, `CustomChart`, and the `Grid`, `Tooltip`, `Legend`, `DataZoom`, `MarkArea` components, plus `CanvasRenderer`. Exports `useEChart(ref, option)`.
  - **`charts.tsx`:** `DetectionsChart` (stacked bars), `PowerChart` (W), `TemperatureChart` (CPU and GPU lines + legend), `FpsChart`, `PipelineBand` (custom series of state segments).
    - every chart has a single y-axis
    - colours come from the tokens: series use the alert colours; temperature uses blue for CPU and orange for GPU, with the legend always shown
    - tooltips use axis-pointer crosshairs
  - **`AnalyticsView`:**
    - mission Select, a KPI tile row, the 5 charts, and a `TelemetryTable` (a Radix Tabs toggle between Charts and Table)
    - **empty state:** `No telemetry recorded for this mission`, with the alert counts still shown (Review Focus 1)
  - **`MissionsView`:** a table from `getMissions()`: name, start, end, duration, alert counts (`alert_counts`) and distance (`distance_m`). Row actions: Replay, Analytics, Report, CSV, GeoJSON, KML. Plus New mission.

- [ ] **Step 1: Write the failing tests**
  - **`metrics.test.ts`:**
    - alerts at start+10 s (fire), start+70 s (person ×2) and a null `received_at` (smoke) give `[{minute: 0, fire: 1, smoke: 1, person: 0}, {minute: 1, person: 2, fire: 0, smoke: 0}]`
    - `summary`: `distanceM` ≈ 111.32 for a 0.001° track; `computeSavedPct` for runs 10 / skipped 30 is 75; null power fields give null averages
    - an empty timeline gives `durationS 0`, `distanceM 0`, and no NaN anywhere (Review Focus 1)
    - **performance:** `summary` + `detectionsPerMinute` on 10 000 samples and 1 000 alerts takes < 50 ms (Review Focus 5)
  - **`analytics-view.test.tsx`** (ECharts mocked): with fixtures, the KPI `Compute saved` shows `75%`; an empty timeline shows the empty-state text.
  - **`missions.test.tsx`:** each row's Report link has `href="/report/<id>"`, and the CSV link has `/api/missions/<id>/export.csv`.
- [ ] **Step 2: Run them, expect FAIL**
- [ ] **Step 3: Implement**
- [ ] **Step 4: `npm test` and `npm run typecheck`, expect PASS. Then `npm run build`, and check that the gzip size of the shell + Live chunks (excluding the lazy `replay`, `analytics` and `echarts` chunks) is ≤ 700 KB. Print the sizes with `gzip -c | wc -c` per file.**
- [ ] **Step 5: Commit** `feat(ui): analytics dashboard and missions view`

---

### Task 11: End-to-end tests, build check, removing the old UI, docs

**Files:**
- Create: `ground_station/web/tests/e2e/{station.spec.ts,offline.spec.ts,mobile.spec.ts}`, `ground_station/web/tests/e2e/fixtures.ts`, `ground_station/web/scripts/check-build.mjs`
- Delete: `ground_station/templates/index.html`, `ground_station/static/app.js`, `ground_station/static/app.css`, `ground_station/static/vendor/leaflet/`
- Modify: `ground_station/web/playwright.config.ts`, `GUIDE.md` (new §13.5, plus the §2.4 wording for the new UI), `PROJECT_STATUS.md` (Round 5), `README.md` (commands)

**Interfaces:**
- **`playwright.config.ts`:**
  - `webServer` starts the station: `${GS_PYTHON ?? "python3"} ground_station/app.py` with `cwd` = the repo root and env `GS_PORT=5077`, `GS_HOST=127.0.0.1`, `GS_DATA_DIR=<os tmp>/gs-e2e-<pid>`, `GS_BEACON_TARGETS=127.0.0.1`, `GS_BEACON_PORT=5099`
  - `url: http://127.0.0.1:5077/health`
  - `baseURL: http://127.0.0.1:5077`; Chromium; `workers: 1`
- **`fixtures.ts`:**
  - a `demoDrone` fixture spawns `${GS_PYTHON} ground_station/demo_drone.py --station http://127.0.0.1:5077 --cycle 30 --db <tmp>` and kills it on teardown
  - an auto-fixture fails the test on any `console.error` or `pageerror`, and records the hosts of every request
- **`check-build.mjs`:** copies `../static/app` to a temp folder, runs `vite build --outDir <tmp2>`, and compares the file lists and `index.html`. Exit code 1 if they differ.

- [ ] **Step 1: Write the e2e tests**
  - **`station.spec.ts`:**
    1. `LIVE` within 10 s; the drone marker's bounding box moves within 3 s; the preview `img` `src` changes
    2. waits ≤ 40 s for an alert toast; opens it from the drawer; Acknowledge → status `acknowledged`; Resolve → `resolved`; Reopen → `acknowledged`
    3. pressing `3` → `window.__gsMap.getPitch() >= 45` (page opened as `/?debug=1#/live`; see Task 7)
    4. Replay: seeking to the start shows 0 alert markers; seeking to the end shows the same count as `/api/missions/<id>/timeline` alerts; clicking an alert tick changes the time label
    5. Analytics: 5 chart canvases render, and the KPI alert total equals the API alert count
    Station-restart recovery is covered by the Task 5 unit tests and the Step 4 manual check (Review Focus 4). Playwright doesn't restart its own webServer.
  - **`offline.spec.ts`:** `page.route(/^(?!http:\/\/127\.0\.0\.1:5077)/, r => r.abort())`, load `/`, see `LIVE` with the demo drone, and **0 aborted requests** in the record (Success criterion 1).
  - **`mobile.spec.ts`:** viewport 375×812 → `document.documentElement.scrollWidth <= 375`; the bottom tabs navigate to Analytics; the alert sheet opens.
- [ ] **Step 2: Run `GS_PYTHON=$PY npm run test:e2e`.** Expect FAIL only where behaviour is missing, then fix in the owning component. Repeat until it passes.
- [ ] **Step 3: Delete the old UI files.**
  - Run pytest; it should pass, since `/` now serves the build. Remove the Leaflet assertions from any test that still references `static/vendor/leaflet`.
  - `npm run build`, then `npm run check:build` → exit code 0.
- [ ] **Step 4: Manual check in the in-app browser** (station + demo drone), with screenshots of:
  - Live in dark mode, then light mode
  - 3D with terrain over the cached area
  - Replay mid-mission and Analytics
  - phone width
  - station killed and restarted while open → `Reconnecting…`, then `LIVE`, plus a toast for an alert posted during the gap (Review Focus 4)
- [ ] **Step 5: Docs.**
  - **`GUIDE.md` §13.5 "Working on the dashboard UI":** Node 22, `cd ground_station/web && npm ci`, `npm run dev` (with `python ground_station/app.py` running), `npm test`, `GS_PYTHON=../../venv/bin/python npm run test:e2e`, `npm run build`, then commit `ground_station/static/app/`.
  - **`GUIDE.md` §2.4:** describes the new UI.
  - **`PROJECT_STATUS.md` Round 5:** a table of the features and the test counts.
  - **`README.md`:** the new commands.
- [ ] **Step 6: Run the full pytest, `npm test`, `npm run typecheck`, `npm run test:e2e` and `npm run check:build`; all should pass. Then commit and push.**
  - `feat(ui): e2e suite, build check, remove v2 UI, docs`
  - `git push` (branch `temp-jetson-fixes`)
