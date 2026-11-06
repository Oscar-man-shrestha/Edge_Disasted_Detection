# Handover: Edge Disaster Detection Drone

**Status date:** 6 Nov 2026 · **Branch:** `temp-jetson-fixes` (64 commits ahead of `main`, **not merged**)
**Repo:** https://github.com/Hisana-07/Edge_Disasted_Detection_Project
**Detailed day-by-day log with every problem, cause and fix:** [LOG.md](LOG.md) (sections 1–31)

---

## 1. In one paragraph

The drone side runs **for real on the Jetson Nano**: a USB webcam feeds a two-stage AI (a cheap motion/fire-colour
filter, then YOLO on the GPU with TensorRT) that detects **people, fire and smoke** and sends GPS-tagged alerts with
a photo and a short video clip to a **ground-station dashboard** on a laptop. It starts by itself at power-on,
works without internet, and passed a 4-hour stability test. **Not done yet:** real GPS (simulated for now), an
outdoor/field test without the USB cable, battery power, and mounting on an actual drone.

All recordings were deleted before handover: the system starts with an empty dashboard.

---

## 2. How it fits together

```
 DRONE: Jetson Nano (Docker container "edge-drone", autostart service "edge-drone")
   Lenovo USB webcam 1280x720
     → Stage 1 gate (OpenCV, ~20 ms): motion vs the frame 0.5 s ago, or fire colours
     → Stage 2 (YOLO, TensorRT FP16): person (YOLOv8n) + fire/smoke (YOLO26n)
         runs when the gate triggers AND at least every 2 s anyway (safety-net scan)
         full-resolution tiles for longer range
     → alert = type + confidence + GPS + photo + 8 s clip, buffered in SQLite (survives link loss)
   GPS: simulated patrol route for now (real u-blox NEO-M8N planned)
        │  Wi-Fi or USB cable. Station found automatically (UDP beacon), shared link key
        ▼
 LAPTOP: ground station (Flask + React dashboard), http://localhost:5050
   live map + drone, camera preview, alerts with photo/clip, replay, analytics, export,
   coordinate search, simulator remote
```

---

## 3. How to run it

### Laptop (ground station)
```bash
cd Edge_Disasted_Detection_Project
./start_station.sh                 # first run creates a small venv/ (no PyTorch needed)
```
Open **http://localhost:5050**. Leave the terminal open. Tests: `venv/bin/python -m pytest -q` (151) and
`cd ground_station/web && npx vitest run` (99) and `npx playwright test` (11 browser tests).

### Drone (Jetson Nano)
- **Power on → everything starts by itself** (service `edge-drone`); about 1–3 min until LIVE on the dashboard.
- USB cable from the laptop: the Nano is **192.168.55.1**, the laptop **192.168.55.100**. `ssh eshaan@192.168.55.1`
  (ask the owner for access; passwords are not in this repo).
- Logs: `journalctl -u edge-drone -f` · restart: `sudo systemctl restart edge-drone` · stop autostart:
  `sudo systemctl disable --now edge-drone`.
- Code lives in `~/Edge_Disasted_Detection_Project` on the Nano. It was **copied** from the laptop (not a git clone):
  after changing code on the laptop, copy the changed files over (`scp`) and restart the service.

### The shared link key
Drone and station must share the same secret in **`.link_key`** at the repo root (git-ignored, never commit it).
It exists on the owner's laptop and on the Nano. A new laptop needs a copy of that file, or set `GS_LINK_KEY=""`
to switch the check off for testing.

---

## 4. Current drone settings (`/etc/default/edge-drone` on the Nano)

| Setting | Value | What it does | To undo |
|---|---|---|---|
| `EDGE_PERSON_WEIGHTS` / `EDGE_FIRE_WEIGHTS` | `*.engine` | TensorRT models (2.3× faster than PyTorch) | `.pt` files |
| `EDGE_SOURCE` | `0` | Lenovo USB webcam | |
| `EDGE_SERVER_URL` | `auto` | finds the laptop by its beacon | fixed `http://<ip>:5050` |
| `EDGE_GPS` | `sim` | **simulated** GPS | `nmea` once the M8N is wired |
| `EDGE_SIM_PATH`, `EDGE_SIM_LOOP` | survey route, `1` | patrols 6 lanes over the park, 7 min a lap | remove the lines |
| `EDGE_SAMPLE_SEC` | `0.25` | looks at 4 frames/s (faster reaction) | remove (= 0.5) |
| `EDGE_PREVIEW_SEC` | `0.5` | dashboard preview every 0.5 s (fine on USB/strong Wi-Fi) | remove (= 1.5, for weak radio) |
| `EDGE_TILES` | `2` | full-resolution tiles: longer range, people **and** fire/smoke | remove (= off) |

Edit with `sudo nano /etc/default/edge-drone`, then `sudo systemctl restart edge-drone`.

---

## 5. What is done (measured, not estimated, unless marked)

| Area | Result |
|---|---|
| Nano setup | JetPack 4.6.1, Docker image `edge-drone` (5.6 GB), headless over USB, autostart, India time |
| Speed | TensorRT: person 150 ms, fire 129 ms (PyTorch 368 / 267 ms). With tiles: 791 ms per check |
| Detection, people | Whole room, standing still included: ~1 m 91–95 %, ~3 m 88–93 %, **~6 m 84–92 %** (with tiles) |
| Detection, fire | Laptop fire video: ~1 m ~80 %, ~3–4 m ~70 %, missed at ~6 m **before** fire tiling (re-test pending) |
| Detection, smoke | Weakest: 30–61 % in tests |
| Stability | 4 h run: no crash, 29–33 °C, no memory leak, 0 false alarms |
| Power (Nano) | 2.5 W idle scanning → **~3.1 W** with all improvements (4.0 W while YOLO busy). Drone motors: 150–400 W |
| Link | Store-and-forward (alerts survive link loss, verified), auto-discovery, link key, 1 alert per event, 8 s clips |
| Dashboard | Quadcopter marker, icon pins, accurate map (0.7 px), coordinate search (Ctrl+K), replay, analytics, export, phone layout |
| Simulation | Patrol flight + **Simulator remote** (manual steering from the dashboard; sim GPS only) |
| Tests | 151 Python, 99 UI, 11 end-to-end browser tests, all passing |

Main bugs found and fixed (details in LOG.md): AI ran on only 1.4 % of frames (gate too strict, "had to touch the
camera"); alert pins drawn up to 300 px from their real position; first alert 17 s late; photos overwritten after
a restart; TensorRT needing internet at every start; replay hiding the newest alert; power sensor unreadable.

---

## 6. What is left (priority order)

1. **Field test** (no USB cable): laptop on the Nano's own Wi-Fi hotspot, outdoors. Measure the **real max range**
   (person walking away 10/20/30/40 m; estimate ~35 m side-on with tiles) and the Wi-Fi range.
2. **Fire re-test at 6 m** with fire tiling on (laptop or TV playing a fire video), plus a **smoke** test.
3. **GPS (NEO-M8N)**: plan in LOG.md §18. Cut the big plug, female jumpers, Nano **off**:
   red → pin 2, black → pin 6, green → pin 8, yellow → pin 10 (swap green/yellow if no data).
   Then `sudo systemctl disable --now nvgetty`, set `EDGE_GPS=nmea`, restart.
4. **Battery power**: 5 V **4–5 A** BEC from the drone battery into the barrel jack (J48 jumper on).
5. **Mount** the Nano + camera; tilt the camera 30–45° forward (people seen from the side are detected much farther).
6. **Change the Nano password** (`passwd`): it was shared during setup.
7. **Review and merge** `temp-jetson-fixes` → `main` (pull request).

Nice to have: drone name "eshaan-desktop" → `EDGE_DRONE_ID=drone-1`; alerts at the same spot as a count badge
that opens on click; bigger mini-charts; smoke-specific training data; Wi-Fi country set to India
(`REGDOMAIN=IN` in `/etc/default/crda`) so 5 GHz networks work.

---

## 7. Known limitations / gotchas

- **Camera placement matters more than anything**: early "range" tests failed because the camera faced a wall
  1 m away. Point it at open space.
- Tiles make each AI check slower (0.8 s): while busy the drone checks ~2 frames/s instead of ~4.
- A person standing in view gets one alert, then a reminder every 60 s (`EDGE_ALERT_REPEAT_SEC`).
- The simulated drone restarts its patrol from lane 1 whenever the service restarts.
- The station is a Flask development server: fine for one laptop, not for internet exposure.
- The Nano's Wi-Fi hotspot ("lowey" phone hotspot was used for internet) was unreliable; downloads need patience.
- Commands with `sudo` must be typed on the Nano (prompt `eshaan@eshaan-desktop`), not on the laptop.

---

## 8. Where things are

| Path | What |
|---|---|
| `run_pipeline.py` | drone main loop |
| `stage1_gate.py`, `stage2_detector.py` | gate, YOLO, tiling, scheduler (safety-net scan) |
| `alert_store.py`, `clip_recorder.py`, `link.py` | alert buffer, clips, drone↔station link |
| `gps_sim.py`, `gps_source.py`, `data/survey_path.csv` | simulated / real GPS |
| `config.py` | every setting and its `EDGE_*` environment variable |
| `jetson/` | Dockerfile, `run_docker.sh`, autostart service, setup script |
| `ground_station/app.py`, `store.py` | station server + database |
| `ground_station/web/` | dashboard source (React); built into `ground_station/static/app` |
| `start_station.sh` | start the station on a laptop |
| `GUIDE.md`, `JETSON.md`, `LOG.md` | step-by-step guide, Jetson reference, full bring-up log |
