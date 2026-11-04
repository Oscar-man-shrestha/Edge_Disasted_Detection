# Ground Station v2 + Live Drone Link Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Live, offline-capable drone ground station. The drone finds the laptop by itself and streams telemetry, camera previews and alerts. The operator gets a polished dashboard with an alert workflow, exports and a printable report.

**Architecture:** The drone pushes over HTTP from one background thread (`link.py`). It discovers the station through a UDP beacon. The station is a Flask app split into focused modules (store, events/SSE, discovery, exports, tiles), and the vanilla-JS dashboard is served with Leaflet stored in the repo.

**Tech Stack:** Python 3.8+ (the drone runs in the JetPack 4 container, Python 3.8), Flask, requests, sqlite3, OpenCV, vanilla JS, Leaflet 1.9.4, pytest.

**Spec:** `docs/superpowers/specs/2026-11-05-ground-station-design.md`

## Global Constraints

- Drone-side code must run on **Python 3.8**. No `match`, no `X | Y` types, no `list[int]` annotations at runtime.
- **No new Python dependencies.** Flask, requests, OpenCV, numpy and pyserial only. The UI uses **no CDN** at all.
- Discovery: UDP port **5005**. Beacon every **2 s** to `GS_BEACON_TARGETS` (default `255.255.255.255,10.42.0.255`). Payload `{"service":"edge-gs","v":1,"port":<http>,"name":<hostname>}`. Station forgotten after **10 s** without a beacon.
- Intervals: telemetry **1.0 s**, preview **1.5 s** (480 wide, JPEG quality 60), alert forwarding **2.0 s**. Link-lost threshold **3 s**. Preview "stale" after **5 s**. Previews over **500 KB** get `413` and must start with `FFD8`.
- Headers: `X-Drone-Id`, `X-Link-Key`. When `GS_LINK_KEY` is set, a wrong or missing key gets **401**.
- Alert statuses: `new`, `acknowledged`, `resolved` only.
- Track thinning: write a point when moved **≥ 2 m** or **≥ 5 s** since the last point.
- Tile prefetch: zoom ≤ **18**, at most **3000** tiles, **0.2 s** between requests, identifying User-Agent `EdgeDisasterGS/1.0 (+repo URL)`.
- Backoff on link errors: 1 → 2 → 4 → 8 s (max).
- Commit to branch `temp-jetson-fixes` only. **Never push `main`.** Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Run tests with `python -m pytest -q -p no:cacheprovider` (laptop venv).

## Review Focus

1. **The station restarts on an existing `station.db` from the current version (old schema).** It should migrate in place and keep every alert. → test in Task 2.
2. **The drone and laptop clocks disagree by minutes or hours.** The link should still show LIVE, because ages use the station's clock. → test in Task 4.
3. **One browser tab stalls or is closed while another is open.** The other tab should keep getting events, and the bus should not grow without limit. → test in Task 3.
4. **Odd or hostile paths:** `/snap/../station.db`, `/tiles/a/b/c.png`, an alert id that doesn't exist. Each should get a 404 or 400, never a file read or a 500. → tests in Tasks 4 and 6.
5. **Telemetry with the `gps` block missing or all-null** (drone running `EDGE_GPS=sim` before start, or the M8N with no fix). It should be accepted, the drone marker hidden, and the UI should not crash. → tests in Task 4 (API) and Task 10 (demo `--no-gps` in the browser).

---

## File map

| File | Responsibility |
|---|---|
| `config.py` (modify) | link settings: `SERVER_URL="auto"`, `DRONE_ID`, `LINK_KEY`, `DISCOVERY_PORT`, `TELEMETRY_INTERVAL_SEC`, `PREVIEW_INTERVAL_SEC`, `PREVIEW_WIDTH`, `PREVIEW_QUALITY`, `ALERT_FORWARD_INTERVAL_SEC` (removes `FORWARD_INTERVAL_SEC`) |
| `system_stats.py` (new) | Jetson temperatures, loads, RAM, power → dict |
| `gps_sim.py`, `gps_source.py` (modify) | `status()` on every GPS class |
| `alert_store.py` (modify) | `forward_pending(base_url, headers)`, `counts()` |
| `link.py` (new) | `LinkState`, `StationFinder`, `DroneLink` |
| `run_pipeline.py`, `forward_now.py` (modify) | use the link |
| `ground_station/store.py` | SQLite: missions, alerts, track |
| `ground_station/events.py` | SSE `EventBus` |
| `ground_station/discovery.py` | `Beacon` thread |
| `ground_station/app.py` (rewrite) | `create_app()` + routes |
| `ground_station/exports.py` | CSV / GeoJSON / KML / report context |
| `ground_station/tiles.py` | tile cache route + prefetch CLI |
| `ground_station/templates/{index,report}.html`, `static/{app.css,app.js}`, `static/vendor/leaflet/*` | UI |
| `ground_station/demo_drone.py` | simulated drone |
| `jetson/hotspot.sh` | Nano Wi-Fi access point |
| `tests/test_system_stats.py`, `tests/test_gs_store.py`, `tests/test_gs_events_discovery.py`, `tests/test_gs_api.py`, `tests/test_gs_exports_tiles.py`, `tests/test_link.py` | tests |

Test import path: `tests/conftest.py` already puts the repo root and `ground_station/` on `sys.path`. Station modules are imported as `store`, `events`, `app`, and so on.

---

### Task 1: Config, system stats, GPS `status()`

**Files:**
- Modify: `config.py`, `gps_sim.py`, `gps_source.py`
- Create: `system_stats.py`
- Test: `tests/test_system_stats.py`, `tests/test_gps.py`, `tests/test_gps_nmea.py`

**Interfaces:**
- Produces: `system_stats.read_stats(root="/") -> dict` with keys `power_mw, cpu_temp_c, gpu_temp_c, cpu_load_pct, gpu_load_pct, ram_used_mb, ram_total_mb` (any of them may be `None`). The class `SystemStats(root="/")` has `.read() -> dict` and remembers the previous `/proc/stat` sample so it can compute CPU load as a delta.
- Produces: `GPSSim.status(t_sec) -> dict`, `NmeaGPS.status() -> dict`, `MavlinkGPS.status() -> dict`. Each returns the keys `mode, fix, lat, lon, alt_m, sats, hdop, speed_mps, course_deg, age_s`.
- Produces: `config.SERVER_URL` defaults to `"auto"`, plus `DRONE_ID` (`EDGE_DRONE_ID`, default `socket.gethostname()`), `LINK_KEY` (`EDGE_LINK_KEY`, default `""`), `DISCOVERY_PORT=5005`, `TELEMETRY_INTERVAL_SEC=1.0`, `PREVIEW_INTERVAL_SEC=1.5`, `PREVIEW_WIDTH=480`, `PREVIEW_QUALITY=60`, and `ALERT_FORWARD_INTERVAL_SEC=2.0` (replaces `FORWARD_INTERVAL_SEC`; update its only user, `run_pipeline.py`, in Task 8).

- [ ] **Step 1: Write failing tests**

`tests/test_system_stats.py`:
- `test_reads_fake_jetson_root(tmp_path)` builds a fake root containing:
  - `sys/devices/virtual/thermal/thermal_zone0/{type="CPU-therm",temp="48500"}`
  - `thermal_zone1/{type="GPU-therm",temp="46000"}`
  - `sys/devices/gpu.0/load="710"`
  - `proc/meminfo` with `MemTotal: 4050944 kB` and `MemAvailable: 1081344 kB`
  - two `proc/stat` samples (rewrite the file between `.read()` calls: `cpu  100 0 100 800 0 0 0` then `cpu  160 0 140 900 0 0 0`)
- It asserts `cpu_temp_c == 48.5`, `gpu_temp_c == 46.0`, `gpu_load_pct == 71.0`, `ram_total_mb == 3956`, `ram_used_mb == 2900`, and the second read has `cpu_load_pct == 50.0` (busy delta 100 over total delta 200).
- `test_missing_everything_returns_nones(tmp_path)`: every value is `None` and nothing raises.

In `tests/test_gps.py`, add `test_sim_status_has_course_and_speed`: at `t=10` the sim is on the first, northbound segment, so the status is `fix is True`, `course_deg == pytest.approx(0, abs=1)`, `speed_mps == 5.0`, `mode == "sim"`.

In `tests/test_gps_nmea.py`, extend the pty test so that after the fix `gps.status()` gives `sats == 9`, `alt_m == 920.4`, `speed_mps == pytest.approx(0.257, abs=1e-3)`, `course_deg == 84.4`, `fix is True`. After the fix goes stale it gives `fix is False`, `lat is None`.

- [ ] **Step 2: Run them, expect FAIL** (`ModuleNotFoundError: system_stats`, `AttributeError: status`)

Run: `python -m pytest -q -p no:cacheprovider tests/test_system_stats.py tests/test_gps.py tests/test_gps_nmea.py`

- [ ] **Step 3: Implement**
- `system_stats.py`: paths are joined under `root`. Power comes from `power_monitor.PowerMonitor()._read` when it is available (only when `root == "/"`). Temperatures are divided by 1000, GPU load by 10. RAM used = total − available, in MiB.
- `GPSSim`: keep the `segment index → bearing` from the last `position()`. Bearing = `atan2(dlon·cos(lat), dlat)` in degrees, normalised to 0–360.
- `NmeaGPS`: store `speed_mps` and `course` from RMC.
- MAVLink: copy `hdg/100`, `alt/1000`, and the speed from `vx,vy`.

- [ ] **Step 4: Run them, expect PASS. Then run the full suite: expect PASS (28 existing tests plus the new ones).**

- [ ] **Step 5: Commit** `feat(drone): system stats, GPS status(), link config`

---

### Task 2: Station store

**Files:**
- Create: `ground_station/store.py`
- Test: `tests/test_gs_store.py`

**Interfaces:**
- Produces: `Store(db_path)`, with:
  - `.current_mission() -> dict` (creates one if none is open), `.new_mission(name=None) -> dict`, `.missions() -> list[dict]`
  - `.add_alert(fields: dict) -> (dict, created: bool)`. `fields` holds `drone_id, drone_alert_id, type, conf, lat, lon, video_time, wall_time`. A duplicate returns the existing row with `created=False` and its status unchanged.
  - `.set_snapshot(alert_id, name)`
  - `.update_alert(alert_id, status=None, note=None) -> dict | None`. Raises `ValueError` for a bad status.
  - `.alerts(mission_id) -> list[dict]`
  - `.add_track_point(drone_id, t, lat, lon, alt_m) -> bool` (`True` if written)
  - `.track(mission_id) -> list[dict]`
- Mission dicts: `id, name, started_at, ended_at`. Alert dicts: every column in spec §5.1.

- [ ] **Step 1: Write failing tests** in `tests/test_gs_store.py`:
- `test_mission_created_on_first_use`
- `test_new_mission_closes_previous`: the old mission has `ended_at` set, and the new id is larger.
- `test_add_alert_dedupes_and_keeps_status`: add, acknowledge, add the same `(drone_alert_id, wall_time)` again → `created is False` and status `acknowledged`.
- `test_update_alert_timestamps`: `acknowledged` sets `acked_at`, `resolved` sets `resolved_at`, `"bogus"` raises `ValueError`, and an unknown id returns `None`.
- `test_track_thinning`: points 1 m apart and 1 s apart aren't written; ≥ 2 m is written; same place after 5 s is written.
- `test_migrates_v1_station_db(tmp_path)`: create the **current** v1 schema by hand (the `CREATE TABLE alerts` and `CREATE UNIQUE INDEX dedupe` from `ground_station/app.py` at commit 488c553) and insert two rows. `Store()` then lists both under mission 1, with status `new`.

- [ ] **Step 2: Run, expect FAIL**
- [ ] **Step 3: Implement `store.py`.** Use WAL, `check_same_thread=False` and a `threading.Lock` around every query. Migrate with `PRAGMA table_info(alerts)` and `ALTER TABLE ADD COLUMN` for `mission_id, drone_id, status, note, acked_at, resolved_at`. Null `mission_id` rows go to the first mission. Track thinning uses equirectangular distance (the same `111320` formula as `gps_sim._dist`) against the last point kept in memory per drone.
- [ ] **Step 4: Run, expect PASS**
- [ ] **Step 5: Commit** `feat(gs): SQLite store with missions, alert workflow, track`

---

### Task 3: SSE event bus + discovery beacon

**Files:**
- Create: `ground_station/events.py`, `ground_station/discovery.py`
- Test: `tests/test_gs_events_discovery.py`

**Interfaces:**
- Produces: `EventBus(max_queue=100)`, with:
  - `.subscribe() -> queue.Queue`
  - `.unsubscribe(q)`
  - `.publish(event: str, data: dict)`: adds `data["server_time"] = time.time()`. A subscriber whose queue is full is removed.
  - `format_sse(event, data) -> str` gives `"event: <e>\ndata: <json>\n\n"`.
  - `.stream(q, heartbeat=15) -> generator of str`: yields `": hb\n\n"` when idle.
- Produces: `Beacon(http_port, targets, beacon_port=5005, interval=2.0)` with `.start()`/`.stop()`, and `beacon_payload(http_port) -> bytes`.

- [ ] **Step 1: Write failing tests**
- `test_publish_reaches_all_subscribers`
- `test_slow_subscriber_dropped_others_keep_receiving`: `max_queue=2`, publish 5 events without draining q1 while draining q2 → q2 has all 5 and q1 is no longer in `bus._subs`.
- `test_format_sse`
- `test_beacon_received_on_localhost`: start `Beacon(5000, ["127.0.0.1"], beacon_port=<free port>, interval=0.1)` and receive with a UDP socket. The JSON has `service == "edge-gs"`, `port == 5000`, `v == 1`.

- [ ] **Step 2: Run, expect FAIL**
- [ ] **Step 3: Implement.** The beacon socket uses `SO_BROADCAST`. A send error on one target (no route) is ignored, so the others still go out.
- [ ] **Step 4: Run, expect PASS**
- [ ] **Step 5: Commit** `feat(gs): SSE event bus and UDP discovery beacon`

---

### Task 4: Station app factory + API

**Files:**
- Rewrite: `ground_station/app.py`
- Modify: `tests/test_ground_station_link.py` (station fixture → `create_app`)
- Test: `tests/test_gs_api.py`

**Interfaces:**
- Consumes: `Store`, `EventBus`, `Beacon` (Tasks 2–3).
- Produces: `create_app(data_dir: str, link_key: str = "") -> Flask`, with `app.config["STORE"]`, `app.config["BUS"]` and `app.config["LIVE"]`. `LIVE` is a dict: `telemetry, received_at, preview_jpeg, preview_t, preview_stage2`.
- Produces: `link_state(live, now) -> {"state": "live"|"lost"|"never", "age_s": float|None}` with a 3 s threshold, based on `received_at` (the station's clock).
- A watcher thread started in `create_app` publishes a `link` event whenever the state changes (checked every 1 s).
- Routes: as in spec §5.2. `/api/stream` is `text/event-stream`, and the first thing it sends is a `hello` event with `server_time`.
- The `__main__` block reads `GS_HOST` (**default changes to `0.0.0.0`**: the beacon tells drones to connect, so the station must be reachable from them; `GS_HOST=127.0.0.1` gives local-only), `GS_PORT`, `GS_DATA_DIR`, `GS_LINK_KEY`, `GS_BEACON_TARGETS`, `GS_BEACON_PORT`. It starts the `Beacon`, then `app.run(threaded=True)`, and prints the dashboard URL.
- `StationFinder` keeps the current station while its beacons keep arriving; a beacon from another address is ignored until the current one has been silent for 10 s.

- [ ] **Step 1: Write failing tests** in `tests/test_gs_api.py` (Flask test client):
- `test_telemetry_accepted_and_state_live`: POST telemetry with `time` set to **10 hours ago** → `/api/state` link `state == "live"` (Review Focus 2).
- `test_telemetry_without_gps_accepted`: bodies `{"drone_id":"x"}` and `{"gps": null}` → 200 (Review Focus 5).
- `test_telemetry_bad_json_400`: a non-JSON body, and `{"gps": "nope"}`.
- `test_link_lost_after_3s`: call `link_state(live, now=received_at+3.5)` and check `state == "lost"`.
- `test_preview_roundtrip`: POST a real `cv2.imencode` JPEG with `X-Stage2-Active: 1` → `/api/preview.jpg` returns the same bytes, and the state shows `preview_stage2 is True`.
- `test_preview_rejects_non_jpeg_and_oversize`: a PNG gets 400, and 600 KB of `b"\xff\xd8" + zeros` gets 413.
- `test_alert_status_update_and_event`: POST `/alert`, subscribe to the bus, POST `/api/alerts/<id>` `{"status":"acknowledged","note":"team sent"}` → 200, the bus received `alert_update`, and the note is stored.
- `test_alert_update_unknown_and_bad_status`: an unknown id gets 404, `"bogus"` gets 400.
- `test_link_key_required_when_set`: `create_app(..., link_key="k")` → POSTs to `/api/telemetry`, `/api/preview` and `/alert` without the header get 401, and with `X-Link-Key: k` get 200. Browser GETs work without the key.
- `test_snap_path_traversal_404`: `/snap/../station.db` and `/snap/%2e%2e/station.db` → 404 (Review Focus 4).
- `test_new_mission_endpoint`: `POST /api/missions` → the new mission id shows in `/api/state`, and a `mission` event is published.
- `test_alerts_json_backcompat`: `/alerts.json` lists alerts in priority order.

Existing `tests/test_ground_station_link.py`: change the `station` fixture to `create_app(str(tmp_path/"gs"))`, served by werkzeug `make_server`. Its assertions stay the same, except the restart check now builds a **new** app on the same `data_dir`.

- [ ] **Step 2: Run, expect FAIL**
- [ ] **Step 3: Implement `app.py`**
- Auth: a `before_request` check on the three drone routes.
- `/snap`: `send_from_directory` with a `os.path.basename(name) == name` check.
- Snapshots are saved to `<data_dir>/snaps/<id>_<type>.jpg`. The old `received/*.jpg` keep working, because the v1 rows store bare filenames: resolve them against `data_dir` first, then `data_dir/snaps`.
- The default `data_dir` is `ground_station/received` (keeps the existing data).
- [ ] **Step 4: Run the full suite, expect PASS**
- [ ] **Step 5: Commit** `feat(gs): app factory, live telemetry/preview API, SSE stream, alert workflow`

---

### Task 5: Exports + printable report

**Files:**
- Create: `ground_station/exports.py`, `ground_station/templates/report.html`
- Modify: `ground_station/app.py` (export and report routes)
- Test: `tests/test_gs_exports_tiles.py`

**Interfaces:**
- Produces:
  - `to_csv(alerts) -> str`, with header `id,mission_id,type,conf,status,lat,lon,wall_time,received,note,snapshot`
  - `to_geojson(alerts, track) -> dict`: a FeatureCollection with Point features (`properties`: type, conf, status, wall_time, note) and one `LineString` feature (`properties.kind == "track"`) when there are ≥ 2 track points. Alerts without lat/lon are skipped.
  - `to_kml(mission, alerts, track) -> str`: `Style` ids `person`, `fire`, `smoke`, one Placemark per located alert, and a `LineString` track.
  - `report_context(mission, alerts, track) -> dict`, with keys `duration_s, distance_m, counts` (`{type: {"total","new","acknowledged","resolved"}}`), `first_detection` (`{type: wall_time}`), `bbox`.
- Routes: `GET /api/missions/<id>/export.<fmt>` (`csv`, `geojson` or `kml`, with a `Content-Disposition` attachment named `mission-<id>.<fmt>`; anything else gets 404), and `GET /report/<id>` (unknown id gets 404).

- [ ] **Step 1: Write failing tests**
- `test_csv_rows_and_header`: 3 alerts → 4 lines, and a note containing a comma survives a round trip through `csv.reader`.
- `test_geojson_valid_and_skips_unlocated`: `json.loads(json.dumps(...))`, the point count equals the located alerts, and there is a track feature.
- `test_kml_parses`: `xml.etree.ElementTree.fromstring`, the Placemark count is located alerts + 1, and a `<` in a note is escaped.
- `test_report_context_numbers`: a two-point track 111.32 m apart (0.001° of latitude) → `distance_m == pytest.approx(111.32, rel=1e-3)`, and the counts are right.
- `test_export_routes`: each format returns 200 with an attachment, `/report/<id>` returns 200 HTML containing the mission name, and `export.exe` gets 404.

- [ ] **Step 2: Run, expect FAIL**
- [ ] **Step 3: Implement.** KML is escaped with `xml.sax.saxutils.escape`. `report.html` is a Jinja template with `@media print` (white background, page breaks avoided inside rows), thumbnails from `/snap/`, and a "Print / Save as PDF" button that is hidden when printed.
- [ ] **Step 4: Run, expect PASS**
- [ ] **Step 5: Commit** `feat(gs): CSV/GeoJSON/KML exports and printable mission report`

---

### Task 6: Offline map tiles

**Files:**
- Create: `ground_station/tiles.py`
- Modify: `ground_station/app.py` (register the blueprint)
- Test: `tests/test_gs_exports_tiles.py`

**Interfaces:**
- Produces:
  - `tiles_blueprint(cache_dir, fetch=None) -> Blueprint`, with route `/tiles/<int:z>/<int:x>/<int:y>.png`. `fetch(z,x,y) -> bytes|None` is injectable for tests; by default it uses `requests` with the User-Agent and a 5 s timeout.
  - `tile_range(lat1, lon1, lat2, lon2, zmin, zmax) -> list[(z,x,y)]`
  - The CLI `python ground_station/tiles.py prefetch --bbox lat1,lon1,lat2,lon2 --zoom 14-18` refuses more than 3000 tiles or a zoom above 18.

- [ ] **Step 1: Write failing tests**
- `test_tile_served_from_cache_without_fetch`
- `test_tile_fetched_then_cached`: the fake fetch is called once across two requests.
- `test_tile_offline_404`: fetch returns `None` → 404.
- `test_tile_bad_coords_404`: `/tiles/a/b/c.png` and `/tiles/5/99999/1.png` (x ≥ 2^z) → 404 (Review Focus 4).
- `test_tile_range_counts`: a known small bbox gives the expected tile count, and the CLI refuses a 3001-tile request.

- [ ] **Step 2: Run, expect FAIL**
- [ ] **Step 3: Implement.** Cache path: `<cache_dir>/<z>/<x>/<y>.png`. Write to a temp file, then `os.replace`. Slippy-map maths: the standard `x = floor((lon+180)/360·2^z)` and `y = floor((1 − ln(tan φ + sec φ)/π)/2·2^z)`.
- [ ] **Step 4: Run, expect PASS**
- [ ] **Step 5: Commit** `feat(gs): cached OSM tile proxy and polite prefetch CLI`

---

### Task 7: Drone link

**Files:**
- Create: `link.py`
- Modify: `alert_store.py`
- Test: `tests/test_link.py`

**Interfaces:**
- Consumes: `config` link settings, `SystemStats`, the GPS `status()` methods (Task 1), and the station `create_app` and `Beacon` in tests (Tasks 3–4).
- Produces:
  - `AlertStore.forward_pending(base_url: str, headers: dict) -> (sent, left)`, posting to `base_url + "/alert"` with `drone_id` in the form.
  - `AlertStore.counts() -> {"buffered": int, "sent": int}`
  - `LinkState()`: `.frame(frame_bgr, gate_result: dict, ran_stage2: bool, stage2_ms: float|None)` and `.detections(dets: list, t: float)`. Both must be cheap (copy references, no encoding) and lock-protected. `.snapshot() -> dict` builds the `pipeline` block of spec §3.2 (fps from the last 10 frame times).
  - `StationFinder(port=config.DISCOVERY_PORT, fixed_url=None)`: `.url() -> str|None` (`None` if no beacon for 10 s), plus `.start()`/`.stop()`. A `fixed_url` ending in `/alert` is cut back.
  - `DroneLink(state: LinkState, gps, finder: StationFinder, stats=None, store_factory=AlertStore)`: `.start()`, `.stop(flush_timeout=5.0)`, and `.status() -> {"station": url|None, "alerts_sent": int}`. Its thread loop runs telemetry, preview and alerts on their own interval timers with backoff.
  - `build_preview(frame, dets, width, quality) -> bytes` draws boxes scaled to the preview size.
- `run_pipeline.py` and `forward_now.py` still call the old `forward_pending()` until Task 8, so keep a temporary fallback: when `base_url` is `None`, use `config.SERVER_URL` if it isn't `"auto"`. Task 8 removes it.

- [ ] **Step 1: Write failing tests** in `tests/test_link.py`:
- `test_station_finder_from_beacon`: a `Beacon` on a free port to `127.0.0.1` → `finder.url() == "http://127.0.0.1:5000"` within 1 s.
- `test_station_finder_forgets_after_10s`: monkeypatch `time.time` forward by 11 s → `None`.
- `test_fixed_url_strips_alert`
- `test_link_delivers_everything`: a real station (`create_app` + werkzeug), a fixed URL, GPSSim, and intervals monkeypatched to 0.1 s. Feed 5 frames plus one fire detection and one stored alert → within 3 s the station has telemetry with `gps.fix True`, a preview, and the alert.
- `test_link_offline_buffers_and_never_blocks`: station URL `http://127.0.0.1:9`; 200 calls to `LinkState.frame` take < 50 ms in total; `counts()["buffered"] == 1`; `stop()` returns within 6 s.
- `test_link_key_header_sent`: the station has `link_key="k"`, the drone `config.LINK_KEY="k"` → the alert arrives. With the wrong key it stays buffered.
- `test_preview_size_and_boxes`: a 640×360 frame → the JPEG decodes to 480×270, and a red box pixel is present when there are detections.

- [ ] **Step 2: Run, expect FAIL**
- [ ] **Step 3: Implement.** One daemon thread with per-channel `next_due` times. On failure a channel's backoff doubles (1/2/4/8 s cap); on success it resets. Telemetry uses `requests.post(json=..., timeout=(config.FORWARD_CONNECT_TIMEOUT, 2))`. The `AlertStore` is created inside the thread. Errors are logged at most once per 10 s per channel.
- [ ] **Step 4: Run the full suite, expect PASS**
- [ ] **Step 5: Commit** `feat(drone): background link with discovery, telemetry, preview, alerts`

---

### Task 8: Pipeline integration

**Files:**
- Modify: `run_pipeline.py`, `forward_now.py`, `config.py` (remove `FORWARD_INTERVAL_SEC`), `alert_store.py` (remove the Task 7 fallback)
- Test: `tests/test_link.py` (add one)

**Interfaces:**
- Consumes: `LinkState`, `StationFinder`, `DroneLink` (Task 7).

- [ ] **Step 1: Write the failing test** `test_run_pipeline_end_to_end(tmp_path, monkeypatch)`:
  - stub `Stage2Detector`, as the scratch `pipe_test.py` did: fire when the orange box is present
  - a synthetic 10 s video (4 s calm, then an orange box)
  - a real station and `EDGE_SERVER_URL` pointing at it
  - `runpy.run_path("run_pipeline.py")`
  - then check that the station has ≥ 1 fire alert, ≥ 1 telemetry, and a preview, and that the drone DB has `buffered == 0`.
- [ ] **Step 2: Run, expect FAIL**
- [ ] **Step 3: Implement**
  - `run_pipeline.py`: create `LinkState`, `StationFinder(fixed_url=None if config.SERVER_URL=="auto" else config.SERVER_URL)` and `DroneLink(state, gps, finder)`, and `link.start()` before the loop.
  - Each frame calls `state.frame(...)`; after Stage 2 call `state.detections(dets, time.time())`.
  - Remove the old forwarding code. Keep the SIGTERM → KeyboardInterrupt handler. On exit call `link.stop()` and print the summary.
  - `forward_now.py`: wait up to 5 s for a station, then `forward_pending`, then print.
- [ ] **Step 4: Run the full suite, expect PASS**
- [ ] **Step 5: Commit** `feat(drone): pipeline uses DroneLink; auto-discovered station by default`

---

### Task 9: Dashboard UI

**Files:**
- Create: `ground_station/templates/index.html`, `ground_station/static/app.css`, `ground_station/static/app.js`, `ground_station/static/vendor/leaflet/{leaflet.js,leaflet.css,images/*.png,LICENSE}`
- Modify: `ground_station/app.py` (`/` renders the template; `static_folder`)
- Test: `tests/test_gs_api.py` (add one)

**Interfaces:**
- Consumes: `/api/state`, `/api/stream` events (`hello`, `telemetry`, `alert`, `alert_update`, `preview`, `link`, `mission`), `/api/alerts/<id>`, `/api/missions`, the export and report routes, `/tiles/...`, and `/api/preview.jpg?t=<preview_t>`.

- [ ] **Step 1: Write the failing test** `test_dashboard_has_no_external_assets`: `GET /` returns 200, and the HTML contains no `http://` or `https://` in any `src=` or `href=`. `/static/vendor/leaflet/leaflet.js` returns 200.
- [ ] **Step 2: Run, expect FAIL**
- [ ] **Step 3: Store Leaflet in the repo.** Download Leaflet 1.9.4 `leaflet.js`, `leaflet.css`, `images/{layers.png,layers-2x.png,marker-icon.png,marker-icon-2x.png,marker-shadow.png}` and `LICENSE` from `https://unpkg.com/leaflet@1.9.4/dist/` (LICENSE from `https://unpkg.com/leaflet@1.9.4/LICENSE`) into `static/vendor/leaflet/`. Check that the `leaflet.js` header says `Leaflet 1.9.4`.
- [ ] **Step 4: Build the UI** to spec §6:
  - CSS custom properties for the theme. A grid of 3 columns at ≥ 1200 px, 2 at ≥ 800 px, otherwise stacked. Pulse keyframes for new alerts.
  - `app.js` modules (plain functions in one file, about 600 lines):
    - `api()`
    - `connectStream()` (with a resync through `/api/state` on `open`)
    - `renderTopBar(state)`
    - `MapView`: drone marker as a rotated CSS triangle `divIcon`, trail polyline, alert circle markers, follow/fit controls. The tile layer is `/tiles/{z}/{x}/{y}.png`.
    - `LivePanel`: preview `<img>` swapped on the `preview` event, stale overlay, cards, and 60-point canvas sparklines for fps and power.
    - `AlertFeed`: cards, filters, actions, lightbox.
    - `Notifier`: toast, WebAudio tones (person 880 → 660 Hz two-tone; fire and smoke single 520 Hz), title flash.
  - Every telemetry field is optional: show "—" for `null`, and hide the drone marker when `gps.fix` is not `true`.
  - Mute state and filters are kept in `localStorage`, wrapped in try/catch.
- [ ] **Step 5: Run the suite, expect PASS. Then do the manual check in Task 10.**
- [ ] **Step 6: Commit** `feat(gs): live ops dashboard (map, live panel, alert workflow), Leaflet vendored`

---

### Task 10: Demo drone + end-to-end browser check

**Files:**
- Create: `ground_station/demo_drone.py`

**Interfaces:**
- Consumes: `link.LinkState`, `StationFinder`, `DroneLink`, `gps_sim.GPSSim`, `alert_store.AlertStore`.
- CLI: `python ground_station/demo_drone.py [--station auto|URL] [--video PATH] [--no-gps] [--speed 5] [--db /tmp/demo_alerts.db]`.
  - It runs `link.py` unchanged, with a GPSSim (or a "no fix" GPS when `--no-gps` is given).
  - Frames come from the video, or are generated: a moving textured scene, with an orange blob from 20 s to 50 s.
  - It raises fire and person alerts during that window, through a real `AlertStore` using a demo DB path.
  - Fake system stats: power 4.5–7.5 W following the pipeline state, temperatures 45–60 °C.
- [ ] **Step 1: Implement `demo_drone.py`**
- [ ] **Step 2: Start the station** (port 5055, temp data dir) **and the demo** (`--station auto`, which exercises the real beacon on localhost) through `.claude/launch.json` and `preview_start`. Open `http://localhost:5055` in the in-app browser.
- [ ] **Step 3: Check with screenshots, one per item:**
  - the LIVE pill
  - the drone moving with its trail
  - the preview refreshing
  - a toast when the first alert arrives
  - Acknowledge changes the card and the marker pulse
  - the CSV, GeoJSON and KML exports download, and the report renders
  - stop the demo → LINK LOST within 4 s
  - `--no-gps` run → no JS console errors and the marker hidden (Review Focus 5)
  - the tile host blocked → the UI still loads, and only uncached map tiles are blank
  - the layout at mobile width (375 px)
- [ ] **Step 4: Fix any problems found. Run the full suite, expect PASS.**
- [ ] **Step 5: Commit** `feat(gs): demo drone for offline demos; e2e verified`

---

### Task 11: Nano hotspot + docs

**Files:**
- Create: `jetson/hotspot.sh`
- Modify: `JETSON.md` (a "Field network" section and an updated live-run section with `EDGE_SERVER_URL=auto`), `jetson/edge-drone.env` (`EDGE_SERVER_URL=auto`), `PROJECT_STATUS.md` (Round 4 + the test count), `README.md` (station section, demo command)

- [ ] **Step 1: Write `hotspot.sh`**
  - Commands: `hotspot.sh [--ssid DRONE-EDGE] [--password PW] [--ifname wlan0]` and `hotspot.sh --off`.
  - Check for `AP` in `iw list` "Supported interface modes", and exit 1 with a message if it isn't there.
  - Create the connection: `nmcli con add type wifi ifname $IF con-name drone-edge autoconnect yes ssid $SSID 802-11-wireless.mode ap 802-11-wireless.band bg ipv4.method shared wifi-sec.key-mgmt wpa-psk wifi-sec.psk $PW`, then `nmcli con up drone-edge`.
  - If no password is given, generate one with `openssl rand -base64 9` and print it once.
  - The script must pass `bash -n`.
- [ ] **Step 2: Update the docs.** Include the field checklist:
  - Nano boots → hotspot up
  - laptop joins `DRONE-EDGE`
  - `python ground_station/app.py` (now listens on all interfaces by default; set `GS_LINK_KEY` on both sides for an extra shared key)
  - the drone appears as LIVE
- [ ] **Step 3: Run the full suite, plus `bash -n jetson/*.sh`**
- [ ] **Step 4: Commit and push** `docs+jetson: field hotspot, ground station v2 docs`, then `git push` (branch `temp-jetson-fixes`)
