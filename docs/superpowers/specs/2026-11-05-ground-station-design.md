# Ground Station v2 + Live Drone Link: Design

**Date:** 2026-11-05 · **Branch:** `temp-jetson-fixes` · **Status:** approved design, awaiting spec review

## 1. Goal and success criteria

**Purpose (agreed):** a polished live dashboard for **project demos and evaluation first**, built so it **also works offline in the field**.

**Hardware:** Jetson Nano B01 on the drone, Lenovo USB webcam, u-blox NEO-M8N GPS. The operator uses a laptop that joins the **Nano's own Wi-Fi hotspot**, so there is no router and no internet.

**Success criteria**
1. The laptop joins the `DRONE-EDGE` hotspot, the operator starts the station, and the drone **finds the station automatically** with no IP typed.
2. Within 2 s of starting, the dashboard shows the drone as **LIVE**: its position and heading on the map, GPS status, pipeline and board status, and a camera preview that refreshes about every 1.5 s.
3. A new alert appears on the dashboard **within 3 s** of being created on the drone, with a toast and a sound. No alert is lost when the link drops; buffered alerts arrive when it comes back.
4. The operator can **acknowledge, resolve and annotate** alerts, and export a mission as **CSV, GeoJSON, KML** and a **printable report**.
5. With no internet: the UI still loads (no CDN), and map tiles the station has seen before are served from its cache.
6. The whole dashboard can be shown **without the Nano** using `demo_drone.py`.
7. The existing automated tests still pass, and the new tests cover the link, the station API, live updates, discovery and exports.

## 2. Approach (chosen: A)

The drone **pushes** to the station. The station **broadcasts a UDP beacon** so the drone can discover it. The station pushes to the browser with **Server-Sent Events (SSE)**.

Rejected options: (B) the station polls the drone. It needs a server on the drone, a rewrite of the tested alert link, and only works on the hotspot. (C) Run the dashboard on the Nano. The data would be lost if the drone is lost.

```
 DRONE (Jetson, Docker, --network host)                     LAPTOP (ground station, Flask)
 ┌───────────────────────────────┐                          ┌──────────────────────────────────┐
 │ run_pipeline.py (frame loop)  │                          │ discovery.py  UDP beacon ──────┐ │
 │   └─ updates LinkState ───────┼──┐                       │                 every 2 s      │ │
 │ link.py DroneLink (thread)    │  │   UDP :5005           │                                │ │
 │   ├─ discovery listener  ◄────┼──┼──────────────────────────────────────────────────────┘ │
 │   ├─ telemetry  1 s  ─────────┼──┼── POST /api/telemetry ─►  store.py (SQLite)            │
 │   ├─ preview  1.5 s ──────────┼──┼── POST /api/preview ───►  events.py (SSE bus) ─► browser│
 │   └─ alerts (buffered) 2 s ───┼──┼── POST /alert ─────────►  exports.py, tiles.py         │
 │ alert_store.py (SQLite)       │  │                       │  templates/, static/ (no CDN)   │
 └───────────────────────────────┘                          └──────────────────────────────────┘
```

## 3. Link protocol

All drone→station requests carry the headers `X-Drone-Id` and, if configured, `X-Link-Key`. If the station has `GS_LINK_KEY` set and the key is missing or wrong, it replies **401**.

### 3.1 Discovery
- The station sends a UDP datagram every 2 s to every address in `GS_BEACON_TARGETS` (default `255.255.255.255,10.42.0.255`) on port `GS_BEACON_PORT` (default **5005**).
- Payload (JSON): `{"service": "edge-gs", "v": 1, "port": <http port>, "name": "<hostname>"}`.
- The drone listens on `0.0.0.0:5005`. When `EDGE_SERVER_URL=auto` (the new default), it uses `http://<sender ip>:<port>`. It switches to a different station only if the current one has sent no beacon for 10 s.
- An explicit `EDGE_SERVER_URL=http://host:port` turns discovery off. For backward compatibility, a value ending in `/alert` is cut back to the base URL.

### 3.2 Telemetry: `POST /api/telemetry` (JSON, every 1 s, only the latest matters)

Every field may be `null`.

```json
{"drone_id": "nano-1", "seq": 812, "time": 1793000000.12, "uptime_s": 412,
 "gps": {"mode": "nmea", "fix": true, "lat": 12.97, "lon": 77.59, "alt_m": 920.4,
         "sats": 9, "hdop": 0.9, "speed_mps": 4.8, "course_deg": 87.0, "age_s": 0.4},
 "pipeline": {"state": "scanning", "fps": 2.0, "frames": 824, "stage1_ms": 6.1,
              "stage2_ms": 142.0, "stage2_runs": 37, "stage2_skipped": 21, "triggers": 58,
              "last_detection": {"type": "fire", "conf": 0.81, "t": 1793000000.0}},
 "system": {"power_mw": 6120, "cpu_temp_c": 48.5, "gpu_temp_c": 46.0,
            "cpu_load_pct": 63, "gpu_load_pct": 71, "ram_used_mb": 2900, "ram_total_mb": 3956},
 "link": {"alerts_buffered": 0, "alerts_sent": 12}}
```

- `pipeline.state` is one of: `"idle"` (no frames for 3 s), `"scanning"` (Stage 1 only), `"active"` (Stage 2 ran within the last 3 s).
- The station replies `200 {"ok": true}`. A malformed body gets `400`.

### 3.3 Preview: `POST /api/preview`
- Body: `image/jpeg`, at most **500 KB** (anything larger gets `413`). Headers: `X-Frame-Time` (unix seconds), `X-Stage2-Active` (`0`/`1`).
- On the drone: 480×270, JPEG quality 60, Stage 2 boxes drawn when they are less than 3 s old. Sent every 1.5 s.
- The station keeps only the latest preview in memory and serves it at `GET /api/preview.jpg`.

### 3.4 Alerts: `POST /alert` (unchanged multipart)
- Adds the `drone_id` field. Dedupe stays on `(drone_alert_id, wall_time)`.
- The drone sends every 2 s from the link thread, in priority order, using store-and-forward as before.

## 4. Drone side

| File | Change |
|---|---|
| `link.py` (new) | **`LinkState`**: a thread-safe holder the frame loop updates (pipeline counters, latest frame, latest detections). **`DroneLink`**: one daemon thread that does discovery, telemetry, preview and alert forwarding on separate timers. It has its own `AlertStore` (SQLite connection per thread). Network errors use backoff (1→2→4→8 s max) and never raise into the frame loop. `stop()` does a final alert flush within a 5 s deadline. |
| `system_stats.py` (new) | Reads Jetson sysfs: thermal zones (`CPU-therm`, `GPU-therm`), `/sys/devices/gpu.0/load`, `/proc/stat` (CPU load delta), `/proc/meminfo`, and instant power through `power_monitor`. Returns `null`s on other operating systems. |
| `gps_sim.py`, `gps_source.py` | Each GPS class gets **`status() -> dict`**, matching the `gps` block in §3.2. NMEA stores speed and course from RMC, and alt, sats and hdop from GGA. The sim works out course from the segment bearing and uses the configured speed. |
| `alert_store.py` | `forward_pending(base_url, headers)`. Sends `drone_id`. Adds `counts()` for buffered and sent. |
| `run_pipeline.py` | Creates `LinkState` + `DroneLink`. Each frame it updates counters and the latest frame; after Stage 2 it updates the detections. Forwarding is removed from the loop. Shutdown calls `link.stop()`. |
| `forward_now.py` | Uses `DroneLink` discovery (waits up to 5 s for a beacon), then flushes alerts. |
| `config.py` | `SERVER_URL` defaults to `"auto"`. New settings: `DRONE_ID` (`EDGE_DRONE_ID`, default hostname), `LINK_KEY` (`EDGE_LINK_KEY`), `DISCOVERY_PORT=5005`, `TELEMETRY_INTERVAL_SEC=1.0`, `PREVIEW_INTERVAL_SEC=1.5`, `PREVIEW_WIDTH=480`, `PREVIEW_QUALITY=60`, `ALERT_FORWARD_INTERVAL_SEC=2.0` (replaces `FORWARD_INTERVAL_SEC`). |

## 5. Station side

The single file `ground_station/app.py` is split up. There is still no build step and no new Python dependencies (Flask only).

| File | Responsibility |
|---|---|
| `app.py` | `create_app(data_dir, link_key)` factory and all routes. `__main__` starts the beacon and the server (`threaded=True`). |
| `store.py` | SQLite (WAL mode, a lock around writes). Tables below. Migrates the existing `station.db` by adding any missing columns. |
| `events.py` | `EventBus`: a bounded queue per SSE subscriber, `publish(event, data)`, and slow clients are dropped. A heartbeat comment every 15 s. |
| `discovery.py` | Beacon thread (§3.1). |
| `exports.py` | CSV, GeoJSON (alerts as points + the track as a LineString), KML (styled placemarks + the track), and the data for the report. |
| `tiles.py` | `GET /tiles/<z>/<x>/<y>.png`: serves from the disk cache, otherwise fetches from OSM (with an identifying User-Agent, timeout 5 s), saves and serves it. Offline and not cached → `404` (the map shows a blank tile). A CLI prefetches a bounding box for zoom ≤ 18, capped at 3000 tiles, one request at a time with a 0.2 s delay, in line with the OSM tile usage policy. |
| `templates/index.html`, `templates/report.html` | Dashboard and printable report. |
| `static/app.css`, `static/app.js` | UI (vanilla JS). |
| `static/vendor/leaflet/` | Leaflet 1.9.4 (`leaflet.js`, `leaflet.css`, `images/`, `LICENSE`, BSD-2), **checked into the repo** so the UI never needs a CDN. |
| `demo_drone.py` | Simulated drone using the real `link.py`: flies `flight_path.csv`, sends previews from a video (`--video`) or a generated scene, raises alerts during the fire part, with realistic telemetry. `--station auto|URL`. |

### 5.1 Data model (station SQLite)

```
missions(id PK, name, started_at, ended_at NULL)
alerts(id PK, mission_id, drone_id, drone_alert_id, type, conf, lat NULL, lon NULL,
       video_time, wall_time, received, snapshot NULL,
       status TEXT DEFAULT 'new' CHECK(status IN ('new','acknowledged','resolved')),
       note TEXT, acked_at, resolved_at)
       UNIQUE(drone_alert_id, wall_time)
track(id PK, mission_id, drone_id, t, lat, lon, alt_m)
```

- A mission is created at startup if none is open. `POST /api/missions` closes the current mission and opens a new one.
- A track point is written when the drone has a fix **and** has moved ≥ 2 m, or 5 s have passed since the last point. Telemetry itself is not stored; only the latest copy is kept in memory.

### 5.2 Station HTTP API

| Method & path | Purpose |
|---|---|
| `GET /` | Dashboard |
| `GET /api/state` | Initial load: the current mission, latest telemetry and link age, alerts for the mission, and the track |
| `GET /api/stream` | SSE events: `telemetry`, `alert`, `alert_update`, `preview` (`{t, stage2}`, the browser then fetches the image), `link` (`live`/`lost`, checked every 1 s with a 3 s threshold), `mission` |
| `POST /api/telemetry`, `POST /api/preview`, `POST /alert` | From the drone (§3) |
| `GET /api/preview.jpg` | Latest preview (`404` if none yet) |
| `POST /api/alerts/<id>` | JSON `{status?, note?}`. Sets `acked_at`/`resolved_at`. Publishes `alert_update`. |
| `GET /api/missions`, `POST /api/missions` | List / start a new mission |
| `GET /api/missions/<id>/export.<csv\|geojson\|kml>` | Downloads |
| `GET /report/<mission_id>` | Printable report |
| `GET /snap/<name>`, `GET /tiles/...`, `GET /health` | Files, tiles, health check |
| `GET /alerts.json` | Kept for backward compatibility |

## 6. Dashboard (UI)

Dark "ops console" theme, responsive: 3 columns at ≥ 1200 px, stacked on tablets and phones.

- **Top bar:**
  - link pill: **LIVE** (green) or **LINK LOST · 12 s** (red, pulsing)
  - GPS: `FIX · 9 sats · HDOP 0.9`, or `NO FIX`
  - mission name and timer
  - counters for person, fire and smoke (new / total)
  - sound toggle, **New mission**, **Export ▾** (CSV, GeoJSON, KML, Report)
- **Map (centre):**
  - drone marker rotated to its course, with a trail polyline
  - alert markers coloured by type; `new` ones pulse, resolved ones are dimmed
  - "follow drone" toggle and "fit all" button
  - clicking a marker selects the alert in the feed
- **Live panel (left):**
  - preview image with timestamp, a **YOLO ACTIVE** badge, and a "stale" overlay when older than 5 s
  - status cards: pipeline state, frame rate, Stage 1 / Stage 2 ms, Stage 2 runs and skips, power (W), CPU and GPU temperature (amber ≥ 70 °C, red ≥ 80 °C), CPU and GPU load, RAM, alerts waiting
  - 60 s sparklines for frame rate and power
- **Alert feed (right):**
  - priority-sorted cards: thumbnail, type badge, confidence, time, coordinates or "no fix", status
  - buttons: Acknowledge, Resolve, Note, Copy coords, Open in Google Maps (online only)
  - filters by type and status
  - the thumbnail opens a lightbox
- **Notifications:**
  - a toast for each new alert
  - a WebAudio beep (person: a distinct two-tone; fire and smoke: a single tone), muted by the toggle
  - the tab title shows `(N) New alerts` while there are unacknowledged alerts
- **Report:**
  - mission summary (duration, distance flown, alert counts, first-detection times), alert table with thumbnails, track extent
  - `@media print` styles, so the browser can save it as a PDF

## 7. Hotspot (`jetson/hotspot.sh`)

- Checks that the Wi-Fi card supports AP mode (`iw list`). Then creates the NetworkManager connection `drone-edge`: SSID `DRONE-EDGE`, WPA2, the password from the argument or a generated one (printed once), band bg, `ipv4.method shared` (Nano = `10.42.0.1`, DHCP for the laptop), autoconnect at boot.
- `--off` turns it off.
- `JETSON.md` gets a "Field network" section.

## 8. Errors and edge cases

- **Drone:** the link thread catches every exception, logs at most once per 10 s per kind, and backs off. Previews and telemetry are dropped while offline. Alerts stay buffered (store-and-forward unchanged). A station that disappears is forgotten after 10 s of no beacons.
- **Station:** validates JSON (wrong types → 400), checks the preview size and that the content is JPEG (it must start with `FFD8`), and allows only the alert statuses `new`, `acknowledged` and `resolved`. SSE clients that fall behind are dropped (the browser reconnects automatically). Tile fetch failures → 404.
- **Browser:** `EventSource` reconnects automatically. On reconnect it calls `/api/state` again to resync. Ages are computed against the station clock (sent in `/api/state` and each event), so drone/laptop clock differences don't matter.
- **Without a GPS fix:** the drone marker is hidden, the last position is shown faded, and alerts show "no fix" (already supported).

## 9. Testing

**Automated (pytest, laptop, no models):**
- `store`: migration from the current schema, missions, alert status changes, dedupe, track thinning
- station API through the Flask test client: telemetry validation, preview size and type, alert status update, `GS_LINK_KEY` 401s, exports (valid CSV, `json.loads` GeoJSON, KML parsed as XML), report renders
- `events`: a subscriber receives published events; slow subscribers are dropped
- discovery: beacon → listener on localhost with a test port; the drone link picks up the URL
- `DroneLink` against a real werkzeug server: telemetry, preview and alerts arrive; while the station is down, alerts are buffered and the frame loop never blocks (`LinkState.update` < 1 ms); `stop()` flushes
- GPS `status()` for sim and NMEA (speed and course)
- `system_stats` returns `null`s off-Jetson and parses sample sysfs/proc files from a fake root

**End to end:** start the station and `demo_drone.py`, open the dashboard in the in-app browser, and check with screenshots: LIVE pill, moving drone and trail, preview updating, an alert arriving with a toast, acknowledge/resolve working, exports downloading, the offline fallback (block the tile host).

**On the Nano (manual, listed in JETSON.md):** hotspot, discovery from Docker (`--network host`), the real webcam preview, M8N telemetry.

## 10. Out of scope (YAGNI)

- More than one drone at a time. `drone_id` is stored, but the UI follows the most recent drone.
- Real video streaming. The preview is about 0.7 fps by design, to save the Wi-Fi link and the Nano's CPU.
- User accounts, HTTPS, the compass/heading sensor, and controlling the drone from the station.
