# Ground Station UI v3: Professional Frontend Design

**Date:** 2026-11-05 · **Branch:** `temp-jetson-fixes` · **Status:** approved design, awaiting spec review
**Builds on:** [Ground Station v2 spec](2026-11-05-ground-station-design.md) (station API, drone link, SQLite store, offline tiles, which are all kept)

## 1. Goal and success criteria

**Purpose (agreed):** a ground station that looks and works like professional drone ground-control software. It's for **demos and evaluation first**, and **still fully offline in the field** (laptop on the Nano's `DRONE-EDGE` hotspot).

**Scope (agreed):** a full visual redesign, plus three new capabilities:
- **Mission replay timeline**
- **3D / tilted GPU map** (MapLibre GL, optional 3D terrain)
- **Analytics dashboard**

Multi-drone support is out of scope.

**Stack (agreed): React + TypeScript + Vite.** The built UI is committed to the repo, so running the station still needs **only Python**.

**Success criteria**
1. `python ground_station/app.py` serves the new UI at `/` with **no requests to any other host**. A Playwright run with all non-localhost traffic blocked passes.
2. **Live view:** with `demo_drone.py`, within 2 s the dashboard shows LIVE, the drone **moves smoothly** (animated between 1 s updates) with its heading, the camera preview updates, and alerts arrive with a pop-up and sound. Acknowledge, Resolve and Reopen all work.
3. **3D:** the map tilts and rotates. With terrain tiles cached, the 3D toggle shows relief. Without them, it shows the flat map with no errors.
4. **Replay:** for any mission, scrubbing the timeline shows the drone and its trail at time *t*, and only the alerts received by *t*. Play runs at 1×, 4× and 16×, and clicking an alert marker on the timeline jumps to it.
5. **Analytics:** for any mission, the headline numbers and charts (detections per minute, power, temperatures, frame rate, pipeline-state band) render from stored data, and the live mission keeps updating.
6. Works at **375 px (phone)**, **768 px (tablet)** and **≥ 1280 px (laptop)** without horizontal scroll. It's usable with the keyboard alone and announces alerts to screen readers.
7. All pytest, Vitest and Playwright suites pass. Running `npm run build` after a clean `npm ci` reproduces the committed build.

## 2. Architecture

```
ground_station/
  app.py, store.py, events.py, discovery.py, exports.py, tiles.py   (Flask station: extended, see §4)
  templates/report.html                                              (printable report: unchanged)
  web/                        ← NEW: frontend source (Vite + React + TS)
    package.json, package-lock.json, vite.config.ts, tsconfig.json, index.html
    src/
      main.tsx, App.tsx, routes.tsx
      lib/      api.ts (typed fetch), sse.ts (EventSource + resync), clock.ts (server time),
                format.ts, geo.ts (interpolation, bearing, distance), prefs.ts (localStorage, safe)
      store/    live.ts (Zustand: link, telemetry, preview, alerts, mission; applies SSE events)
      features/ shell/ (CommandBar, NavRail, CommandPalette, Toasts, PersonBanner)
                map/ (MissionMap: MapLibre, layers, drone animation, 3D/terrain, controls)
                live/ (LiveView, CameraCard, FlightHud, gauges)
                alerts/ (AlertDrawer, AlertList, AlertDetail, filters)
                replay/ (ReplayView, Timeline, replay state)
                analytics/ (AnalyticsView, KPI tiles, charts)
                missions/ (MissionsView: list, open report, exports)
      ui/       shared primitives (Button, Badge, Card, Dialog, Sheet, Tooltip, Select, Kbd…)
      styles/   tokens.css (colour/spacing/type tokens, dark + light), index.css (Tailwind)
    tests/      unit/ (Vitest), e2e/ (Playwright)
  static/app/                 ← NEW: committed build output (index.html + hashed assets)
```

- **Removed:** `templates/index.html`, `static/app.js`, `static/app.css`, `static/vendor/leaflet/`.
- **Serving:** Flask's `/` returns `static/app/index.html`, and assets load from `/static/app/assets/…` (Vite `base: "/static/app/"`). Navigating between views uses hash routes (`#/live`, `#/replay/:missionId`, `#/analytics/:missionId`, `#/missions`), so Flask needs no new page routes.
- **Development:** `npm run dev` (Vite on :5173) passes `/api`, `/alert`, `/snap`, `/tiles`, `/terrain`, `/report` and `/health` through to Flask on :5000.
- **Toolchain:** Node 22 LTS (Node ≥ 20.19). Exact versions are pinned in `package-lock.json`, and every dependency must have been published for at least 14 days.

### 2.1 Libraries (current major versions)

| Concern | Choice | Why |
|---|---|---|
| UI framework | React 19 + TypeScript (strict) | the most widely known, typed |
| Build | Vite 8 | fast builds, splitting code per view, dev server that passes requests to Flask |
| Map | **MapLibre GL 6** | GPU rendering, tilt and rotate, raster and terrain sources, clustering, open source (BSD) |
| Charts | **Apache ECharts 6**, importing only the chart types used | time-series zoom, large data, a theme we control |
| Styling | **Tailwind CSS 4** + CSS custom-property tokens | consistent design system, dark and light themes |
| Components | **Radix UI** primitives (Dialog, DropdownMenu, Tooltip, Select, Tabs, Slider, ToggleGroup) in shadcn-style wrappers, **cmdk** (command palette), **sonner** (pop-ups), **lucide-react** (icons) | accessible by default |
| State and data | **Zustand** (live store) + **TanStack Query 5** (missions, timelines) | live updates go into the store; history is fetched |
| Routing | **wouter** with hash location | small, and Flask needs no changes |
| Fonts | `@fontsource/inter`, `@fontsource/jetbrains-mono` (bundled) | no Google Fonts request |
| Tests | **Vitest** + Testing Library + jsdom; **Playwright** (Chromium) | unit, component and real end-to-end tests |

## 3. Interface

### 3.1 App shell
- **Command bar (top):**
  - product mark, plus a mission picker with the mission name and live timer (computed from server time)
  - link pill: `LIVE · <drone>`, `LINK LOST · 12 s` or `WAITING FOR DRONE`
  - GPS chip: `FIX · 9 sats · HDOP 0.9`, `NO FIX` or `SIM GPS`
  - alert counters per type (new/total), mute toggle, **⌘K** button, Export menu (CSV, GeoJSON, KML, Report), New mission
- **Navigation rail (left):** Live · Replay · Analytics · Missions. At < 768 px it becomes a bottom tab bar.
- **Command palette (⌘K / Ctrl+K):** jump to a view, open a mission, fly to an alert, toggle 3D / follow / theme / mute, start a new mission, export.
- **Notifications:**
  - a pop-up for every new alert (the same rules as v2, including alerts missed during a reconnect)
  - WebAudio tones: person = two-tone 880 → 660 Hz, fire and smoke = 520 Hz
  - for a **person** alert, a red banner stays until it is acknowledged
  - the tab title shows `(N) New alerts`
  - an `aria-live="assertive"` region announces each alert to screen readers
- **Keyboard shortcuts:**

  | Key | Action |
  |---|---|
  | `A` | acknowledge the selected alert |
  | `R` | resolve the selected alert |
  | `F` | follow the drone |
  | `3` | toggle 3D |
  | `N` | north-up |
  | `Space` | play/pause (Replay) |
  | `←` `→` | step 10 s (Replay) |
  | `?` | shortcut help |

  Shortcuts are ignored while typing in an input.

### 3.2 Live view (default)
- **Full-bleed MapLibre map:**
  - the basemap is the cached OSM raster from `/tiles/{z}/{x}/{y}.png`
  - the drone marker rotates to its course. Its position is **interpolated** between telemetry samples with `requestAnimationFrame`, so it glides rather than jumping every second.
  - the trail is a gradient line, faded where it's old
  - alert markers are coloured by type and carry a letter (P/F/S); new ones pulse
  - **clustering** above 25 alerts, with counts per type in the cluster badge
- **Map controls:** zoom, compass and north-up, **2D/3D** (60° tilt, plus terrain when it's available), heading-up, follow, fit-all, and a layers popover (trail, alerts, terrain, basemap dimming).
- **Floating panels** (they collapse into sheets on mobile):
  - **Camera card:**
    - the live preview with an age label and a `YOLO ACTIVE` badge
    - after 5 s without a new image, a `STALE` overlay
    - expands to full screen, and the detection boxes are visible because they're drawn into the preview by the drone
  - **Flight readout:**
    - compass dial with heading, speed (m/s), altitude, satellites and HDOP
    - pipeline state, frame rate, and Stage 1 / Stage 2 ms
    - YOLO runs and skips, power (W) as a radial gauge, CPU and GPU temperatures (warning ≥ 70 °C, critical ≥ 80 °C, with a label as well as a colour), loads, RAM, and alerts waiting on the drone
    - 60 s sparklines for frame rate and power, with a hover readout
  - **Alert drawer (right):**
    - **list:** priority then newest, with filters by type and status (Open, All, New, Acknowledged, Resolved)
    - **detail sheet:**
      - zoomable snapshot
      - type, confidence, position (copy, and "fly to" on the map) or "no GPS fix"
      - the station's received time, plus the acked and resolved times
      - note editor and the Acknowledge / Resolve / Reopen buttons

### 3.3 Replay view (`#/replay/:missionId`)
- Mission picker. The data comes from `GET /api/missions/<id>/timeline`.
- **Timeline bar:**
  - play/pause, speed 1× / 4× / 16×, a scrubber with time labels
  - alert ticks coloured by type (clicking one jumps there), and a pipeline-state band (idle, scanning, active)
- **The map at time *t*:**
  - the drone is placed by interpolating the stored samples, and the trail shows only up to *t*
  - only alerts with `received_at ≤ t` are shown, and they appear as the playhead passes them
- **Side panel:** the telemetry values nearest *t*, plus the most recent alert's snapshot.
- **Replaying the current, still-running mission** works. It stops at the newest data, with a "jump to live" button.

### 3.4 Analytics view (`#/analytics/:missionId`)
- **Headline numbers:**
  - alerts per type (open/total), mission duration, distance flown
  - YOLO runs vs skipped (**the compute saving from gating**, %)
  - average and peak power, peak temperatures
- **Charts** (ECharts, dataviz rules: one y-axis per chart, a legend whenever there are two or more series, hover tooltips, the validated palette):
  - detections per minute, stacked by type (bars)
  - board power (W, line)
  - CPU and GPU temperature (°C, two lines, legend)
  - frame rate (line)
  - pipeline-state band over time
- **Table view** of the telemetry samples (accessibility, and the data behind the charts).
- **For the live mission**, the analytics refetch the timeline every 30 s.

### 3.5 Missions view (`#/missions`)
- A table of all missions: name, start and end, duration, alert counts, distance.
- Actions per row: Replay, Analytics, Report (opens `/report/<id>`), and CSV / GeoJSON / KML downloads.
- New mission (with a name).

### 3.6 Visual design
- **Themes:** dark (default, "ops console") and light. Both are defined as tokens under `:root` and `[data-theme]`. The choice is remembered, and on first visit it follows the OS setting.
- **Alert colours** (validated in v2, all pairs pass on the dark surface): person `#3987e5`, fire `#d95926`, smoke `#199e70`. Light-theme steps are validated against the light surface before use.
- **Status colours are reserved** for state only: good `#0ca30c`, warning `#fab219`, serious `#ec835a`, critical `#d03b3b`. They always come with a label or icon.
- **Type and motion:**
  - Inter for UI text; JetBrains Mono (tabular) for numbers, coordinates and timers
  - 4 px spacing grid; 8 / 12 px radii
  - motion of 150–250 ms, and **`prefers-reduced-motion` turns off pulses and map fly animations**

## 4. Station (backend) changes

### 4.1 Data model additions (migrated in place, like v2)

```
missions   + started_ts REAL, ended_ts REAL          (unix seconds; filled from existing text for old rows)
alerts     + received_at REAL                         (unix seconds, station clock; old rows: NULL)
telemetry_log(id PK, mission_id, drone_id, t REAL, lat, lon, alt_m, speed_mps, course_deg,
              sats, fix INTEGER, fps, state TEXT, stage2_runs, stage2_skipped,
              power_mw, cpu_temp_c, gpu_temp_c, cpu_load_pct, gpu_load_pct)
```

- **One telemetry sample is stored per drone every ≥ 5 s.** It's taken from received telemetry; non-finite numbers are stored as NULL.
- At 5 s per sample, a 1-hour flight is about 720 rows.

### 4.2 API additions and changes

| Method & path | Behaviour |
|---|---|
| `GET /` | serves `static/app/index.html` (`Cache-Control: no-cache`) |
| `GET /api/missions/<id>/timeline` | `{mission, server_time, track: [{t,lat,lon,alt_m}], telemetry: [telemetry_log rows], alerts: [alerts incl. received_at]}`. Unknown id → 404 |
| `GET /api/state`, `GET /api/missions` | missions now include `started_ts` / `ended_ts` |
| `POST /api/alerts/<id>` | Reopen (`status: "new"` or `"acknowledged"`) clears `resolved_at`. A body that isn't a JSON object → 400 |
| `POST /api/missions` | a body that isn't a JSON object → 400 |
| `GET /terrain/<z>/<x>/<y>.png` | cache proxy for **AWS Terrain Tiles (Terrarium encoding)**: `https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png`. Zoom 0–15, the same disk cache, offline backoff and 404 rules as `/tiles` |
| `tiles.py prefetch … --terrain` | also prefetches terrain tiles for the same box (zoom ≤ 15). The same 3000-tile cap applies to the combined total |

- **Attribution** shown on the map: "© OpenStreetMap contributors · Terrain: Mapzen, AWS Terrain Tiles".

## 5. Data flow in the UI

1. **On load:**
   - `GET /api/state` seeds the Zustand live store: mission, link, telemetry, preview, alerts and track. It also works out the offset between the browser clock and the server clock.
   - `EventSource('/api/stream')` then applies `telemetry`, `preview`, `alert`, `alert_update`, `link` and `mission` events to the store.
   - **Every (re)connect re-fetches `/api/state`** and shows a pop-up for new alerts that weren't seen before (the v2 rule).
2. **Link age** is always measured against server time, so clock differences between drone, station and browser don't matter.
3. **Replay and Analytics** use TanStack Query on `/api/missions/<id>/timeline` (cached per mission). The live mission's query refetches every 30 s, and Live view itself never needs it.
4. **Commands** (acknowledge, resolve, note, new mission) are plain POSTs. The screen updates from the server's reply and the matching live event; there are no optimistic updates that could disagree with the server.

## 6. Failure handling

- **Live updates drop:** a "Reconnecting…" pill shows, it retries with backoff, and it resyncs on reconnect.
- **One panel crashes** (React error boundary): a card shows "This panel failed — Reload panel", and the rest of the app keeps running.
- **Map tile 404s** (offline and not cached): a dark grid background shows through. **Terrain unavailable:** the 3D toggle tilts the flat map and shows a hint ("terrain not cached").
- **No WebGL:** MapLibre isn't started. A notice explains the map needs WebGL, and the camera, flight readout, alerts, Replay and Analytics charts keep working.
- **Telemetry fields that are null or missing** show as "—" everywhere. The drone marker is hidden without a fix, and its last position is shown faded.
- **Network errors on commands:** an error pop-up, and the alert keeps its previous state.

## 7. Testing

- **pytest (backend):**
  - upgrading a v2 `station.db` (`received_at`, `started_ts`, `telemetry_log`)
  - telemetry sampling every 5 s, and non-finite values stored as NULL
  - the timeline endpoint's shape and its 404
  - Reopen clearing `resolved_at`, and non-object JSON → 400
  - the terrain proxy (cached / fetched once / offline 404 and backoff / bad coordinates / z > 15 → 404)
  - prefetch `--terrain` counts
  - `/` serving the built `index.html`
- **Vitest (unit and component):**
  - the store applying each event type (and ignoring other missions)
  - the missed-alert pop-up rule
  - replay interpolation (position and heading at *t*, wrapping across 360°)
  - alert visibility at *t*, playback speed
  - detections-per-minute bucketing, distance and compute-saved maths
  - formatting
  - the alert detail buttons sending the right request
  - shortcut handling (ignored while typing)
- **Playwright (end to end, Chromium)**, against the real Flask station (temp data folder, a fixed port) and `demo_drone.py`:
  1. LIVE within 5 s; the drone marker's position changes over 3 s; the preview `src` changes
  2. an alert arrives (pop-up, drawer item); Acknowledge then Resolve then Reopen
  3. the 3D toggle sets the map pitch to ≥ 45°
  4. Replay: scrubbing to the start shows 0 alerts, to the end shows them all; clicking an alert tick moves the playhead
  5. Analytics: all charts render, and the headline numbers match the API data
  6. the whole run with **every non-localhost request aborted** passes, and no request goes to another host
  7. 375 px viewport: no horizontal scroll, and the bottom tabs work
  8. no console errors in any test
- **Build check:** `npm run build` output matches the committed `static/app/`. A small script compares the asset list and `index.html`.

## 8. Performance budget

- The first load (shell + Live view) is ≤ 700 KB compressed JavaScript. Replay and Analytics are separate chunks that load on demand.
- Map animation and gauge updates run at 60 fps on a typical laptop. Live updates are batched into one React update per animation frame.
- The alert list stays smooth past 500 alerts, by grouping updates and memoising the rows.

## 9. Docs

- **GUIDE.md:** a new section, "13.5 Working on the dashboard UI": install Node 22, `cd ground_station/web && npm ci`, `npm run dev`, `npm test`, `npm run test:e2e`, and `npm run build`, then **commit `static/app/`**.
- **PROJECT_STATUS.md:** Round 5.
- **README:** a screenshot section (optional) and the new commands.

## 10. Out of scope (YAGNI)

- Multi-drone UI, user accounts, HTTPS.
- Recording the video preview for replay (replay shows the alert snapshots instead).
- Vector basemaps or 3D buildings (they need large offline vector-tile downloads).
- A PWA or service worker (the station already serves everything locally).
