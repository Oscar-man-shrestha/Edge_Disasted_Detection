# Project Status: Drone Edge Disaster Detection

**Branch:** `temp-jetson-fixes` (not merged into `main`)
**Last updated:** 2026-11-05
**Hardware:** NVIDIA Jetson Nano Developer Kit B01 · Lenovo USB webcam · u-blox NEO-M8N GPS with compass
**Hardware setup guide:** [JETSON.md](JETSON.md)

This page explains what the project already had on `main`, what this branch changes, how it was tested, and what is still open.

---

## 1. What the project does

A drone-mounted pipeline that detects **fire, smoke and people** without internet, using edge compute only.

```
USB webcam / video
   │  one frame every 0.5 s, resized to 640x360
   ▼
Stage 1 gate (OpenCV, a few ms)    fire-coloured pixels  OR  real change after cancelling drone motion
   │  3 flagged frames in a row
   ▼
Stage 2 scheduler                  every triggered frame until confirmed, then every 3rd
   ▼
Stage 2 detector (YOLO)            YOLOv8n → person    +    fire_smoke.pt → fire, smoke
   │
   ▼
GPS tag (NEO-M8N, or simulated) → SQLite buffer on the drone → HTTP POST every 5 s → Ground station
                                                                                    (map + table + SQLite)
```

The idea is **adaptive compute**: the heavy YOLO models run only when the cheap gate sees something. This saves time and power on the Jetson.

---

## 2. What already existed on `main`

| File | Role |
|---|---|
| `config.py` | All settings in one place |
| `frame_source.py` | Samples frames from a video or camera |
| `stage1_gate.py` | Cheap colour + motion check |
| `stage2_detector.py` | YOLO person + fire/smoke detection |
| `gps_sim.py` | Simulated GPS along `data/flight_path.csv` |
| `alert_store.py` | Cooldown, snapshot, SQLite, forwarding by priority (person > fire > smoke) |
| `run_pipeline.py` | Full pipeline |
| `ground_station/app.py` | Flask server with a Leaflet map and alerts table |
| `benchmark.py` | Gated pipeline vs. heavy model on every frame |
| `export_trt.py`, `make_mixed_video.py`, `test_*.py`, `check_fire_model.py` | Tools and manual check scripts |

**Laptop benchmark on `main`** (CPU, one clip): Stage 2 woke on 53% of frames, **43.8% compute saved**, 0 false triggers on calm frames, fire confirmed 0.96 s after onset. **There are no Jetson numbers yet.**

---

## 3. What this branch changes

### Round 1: Jetson bring-up blockers

| # | Problem on `main` | Fix |
|---|---|---|
| 1 | The README listed environment variables (`EDGE_DEVICE` etc.) that **no code read**, so Jetson runs would quietly use the CPU and the `.pt` weights | `config.py` reads them |
| 2 | Camera pipeline strings were treated as video files (wrong timing) | Correct handling of `csi`, GStreamer and URL sources |
| 3 | The ground station only listened on `127.0.0.1` | `GS_HOST` / `GS_PORT` |

### Round 2: making the alert link reliable

| # | Problem on `main` | Fix |
|---|---|---|
| 4 | Alerts were only sent after the video ended. **A live camera never ends, so no alert would ever be sent.** | Sent every 5 s during the run. Ctrl+C, `docker stop` and `systemctl stop` all send what is left before exiting. |
| 5 | A dead link froze the frame loop for 3 s per try | 1 s connect timeout |
| 6 | One missing snapshot blocked every later alert | The alert is sent without the image |
| 7 | A resend after a lost reply showed up twice | The station ignores alerts it has already received |

### Round 3: features for the real hardware

| # | What | Why it matters | Files |
|---|---|---|---|
| 8 | **Camera-motion compensation in Stage 1.** Tracks ~100 corners between frames, estimates the drone's movement, aligns the previous frame, and only then compares. | Without it, **a moving drone triggers Stage 2 on almost every frame** and the gating saves nothing. In the test, panning went from 15% "changed pixels" (triggers) to 0%, while a real moving object is still caught. | `stage1_gate.py` |
| 9 | **Stage 2 scheduler.** Once a fire or person is confirmed, YOLO runs only every 3rd triggered frame while detections continue. It goes back to every frame when the detections stop. | Alerts have a 10 s cooldown, so the skipped runs would only have produced duplicates. Saves GPU time and heat. In the test, Stage 2 ran 4 times instead of 10 during a sustained fire. | `stage2_detector.py` |
| 10 | **NEO-M8N GPS support** (`EDGE_GPS=nmea`). Reads standard NMEA (RMC + GGA) over the Nano UART or a USB-serial adapter, finds the baud rate automatically, and ignores fixes older than 5 s. | Real coordinates on alerts. Alerts without a fix are still sent and show "no fix". | `gps_source.py` |
| 11 | MAVLink GPS (`EDGE_GPS=mavlink`) | For later, if a flight controller is added | `gps_source.py` |
| 12 | **USB webcam tuning:** asks for MJPG at 1280×720 with a 1-frame buffer | The Lenovo webcam runs at full frame rate with less lag | `frame_source.py` |
| 13 | **Power and energy measurement.** Reads the Nano's power sensor, with `tegrastats` as a fallback. | Energy per frame is the key result for an edge project | `power_monitor.py` |
| 14 | **Better benchmark:** energy (J/frame), uses the scheduler, `--source` / `--tag` options, results saved per tag | Runs with PyTorch and with TensorRT no longer overwrite each other | `benchmark.py` |
| 15 | **Ground station keeps alerts after a restart** (SQLite). The map works offline (plain grid when map tiles cannot load). Added a `/health` endpoint. | Field use without internet | `ground_station/app.py` |
| 16 | **Jetson tooling:** Docker image, run script, one-time setup script, autostart at boot (systemd), CSI camera bridge, TensorRT and ONNX export | Setting up the board takes a few commands; the drone runs with no monitor attached | `jetson/*`, `export_*.py` |
| 17 | **Automated tests:** 28 pytest tests | Teammates can check changes without the models or the board | `tests/`, `pytest.ini` |
| 18 | **Hardware guide** for our parts: power, GPS wiring, webcam, bring-up order, troubleshooting | | `JETSON.md` |

### All settings (environment variables)

| Variable | Default | Meaning |
|---|---|---|
| `EDGE_SOURCE` | `data/mixed_test.mp4` | video, `0` (USB webcam), `csi`, GStreamer pipeline, or MJPEG URL |
| `EDGE_DEVICE` | `cpu` | `0` = Jetson GPU |
| `EDGE_PERSON_WEIGHTS` / `EDGE_FIRE_WEIGHTS` | `weights/*.pt` | `.pt`, `.engine` or `.onnx` |
| `EDGE_SERVER_URL` | `http://localhost:5000/alert` | ground station |
| `EDGE_GPS` | `sim` | `sim`, `nmea` (M8N) or `mavlink` |
| `EDGE_GPS_PORT` / `EDGE_GPS_BAUD` | `/dev/ttyTHS1` / auto | M8N serial port |
| `EDGE_MOTION_COMP` | `1` | Stage 1 motion compensation |
| `EDGE_STAGE2_EVERY_N` | `3` | Stage 2 frequency while confirmed (`1` = old behaviour) |
| `GS_HOST` / `GS_PORT` / `GS_DATA_DIR` | `127.0.0.1` / `5000` / `ground_station/received` | ground station |

---

## 4. How it was tested

**Automated: `python -m pytest`, 28 of 28 pass** (laptop, no models needed)

| Area | What the tests check |
|---|---|
| Stage 1 | orange triggers after 3 frames; a still scene never triggers; panning **triggers without** compensation and **does not trigger with** it; a real moving object is still caught while panning; a blank frame does not crash it |
| Scheduler | every frame until confirmed; every 3rd while confirmed; resets when the trigger drops or a run finds nothing; `N=1` matches the old behaviour |
| GPS (NMEA) | checksum; RMC and GGA parsing; south/west coordinates negative; no-fix sentences; **end to end over a fake serial port**: auto-baud, no fix → fix → stale fix becomes "no fix" |
| GPS (sim) | start, end and hold position; speed |
| Power | parsing `tegrastats` output from JetPack 4 and JetPack 5; energy calculation; still works with no sensor |
| Alert link | offline buffering; cooldown; person threshold; **real HTTP to the ground station**: priority order, missing snapshot, alert with no GPS fix, resends ignored, alerts kept after a station restart |

**Manual (laptop):**
- Full `run_pipeline.py` and `benchmark.py` on a made-up video with a stand-in for YOLO: alerts raised, the scheduler skipped 6 of 10 Stage 2 runs, and buffered alerts did not stall the loop.
- Camera bridge: served a video as an MJPEG stream, which `FrameSource` read as a camera.

**Not tested yet (needs the board or the hardware):** real YOLO and TensorRT on the Nano, power readings, the Lenovo webcam on the Nano, the M8N wired to the UART, Docker and systemd on the board, Stage 1 motion compensation on real drone footage, and Stage 1 speed on the Nano's CPU (about 8 ms on the laptop).

---

## 5. Running it

Follow **[JETSON.md](JETSON.md)**. Short version:

```bash
jetson/setup_nano.sh                                                          # once
EDGE_DEVICE=0 jetson/run_docker.sh python3 check_fire_model.py data/mixed_test.mp4
EDGE_DEVICE=0 jetson/run_docker.sh python3 benchmark.py --tag nano_pytorch
jetson/run_docker.sh python3 export_trt.py
EDGE_DEVICE=0 EDGE_PERSON_WEIGHTS=weights/yolov8n.engine EDGE_FIRE_WEIGHTS=weights/fire_smoke.engine \
  jetson/run_docker.sh python3 benchmark.py --tag nano_trt
```

---

## 6. Still open

| Priority | Item | Notes |
|---|---|---|
| High | **Run the bring-up order in JETSON.md on the Nano** | Steps 1–7 |
| High | **Check that YOLO26 loads on JetPack 4** | Fallbacks are in JETSON.md: rebuild with a newer Ultralytics, or ONNX |
| High | **Jetson benchmark: PyTorch vs. TensorRT, time and energy** | The main result of the project |
| High | **Wire and test the M8N outdoors** | Check the cable's wire order first (see JETSON.md) |
| Medium | Test Stage 1 on real drone footage | Tune `DIFF_FRACTION`; measure motion-compensation time on the Nano CPU |
| Medium | Stress-test the colour gate on orange terrain, sunsets and red roofs | Risk of false triggers |
| Medium | Test person detection on aerial footage | The YOLOv8n COCO model is weak on small, top-down people. May need a model fine-tuned on aerial images (e.g. VisDrone). |
| Low | Use the compass for heading | Lets you estimate where a detection is on the ground, not just where the drone is |
| Low | Alerts are sent over HTTP with no authentication | Fine on a private link; add a shared key before any public network |
