# Project Status: Drone Edge Disaster Detection

**Branch:** `temp-jetson-fixes` (not merged into `main`)
**Date:** 2026-11-05
**Hardware:** NVIDIA Jetson Nano Developer Kit B01 (P3450), in a 3D-printed case with a 40 mm fan and a Wi-Fi antenna

This page explains what the project already had on `main`, what this branch changes, and what is still open.

---

## 1. What the project does

A drone-mounted pipeline that detects **fire, smoke and people** without internet, using edge compute only.

```
camera / video
   │  one frame every 0.5 s, resized to 640x360
   ▼
Stage 1 gate (OpenCV, ~1 ms)      fire-coloured pixels  OR  large frame-to-frame change
   │  3 flagged frames in a row
   ▼
Stage 2 detector (YOLO)           YOLOv8n → person    +    fire_smoke.pt → fire, smoke
   │
   ▼
GPS tag (simulated flight path) → SQLite buffer on the drone → HTTP POST → Ground station (map + table)
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
| `gps_sim.py` | Simulated GPS along `data/flight_path.csv` at 5 m/s |
| `alert_store.py` | 10 s cooldown per type, snapshot with box, SQLite, forwarding by priority (person > fire > smoke) |
| `run_pipeline.py` | Full pipeline |
| `ground_station/app.py` | Flask server with a Leaflet map and alerts table |
| `benchmark.py` | Gated pipeline vs. heavy model on every frame |
| `export_trt.py` | TensorRT FP16 export on the Jetson |
| `make_mixed_video.py` | Builds the calm-then-fire test video and its label file |
| `test_*.py`, `check_fire_model.py` | Manual check scripts |

### Laptop benchmark results (from `main`)

| Metric | Result |
|---|---|
| Frames that woke Stage 2 | 57 of 107 (53.3%) |
| Heavy model on every frame | 8.26 s |
| Gated pipeline | 4.64 s (**43.8% saved**) |
| False triggers on calm frames | 0 |
| Fire confirmed after onset | 0.96 s |

These numbers come from a laptop CPU on one test clip. **There are no Jetson numbers yet.**

---

## 3. What this branch changes

### Round 1: Jetson bring-up blockers

| # | Problem on `main` | Fix | Files |
|---|---|---|---|
| 1 | The README told you to set `EDGE_DEVICE=0`, `EDGE_PERSON_WEIGHTS` and other variables, but **no code read them**. Jetson runs would quietly use the CPU and the `.pt` weights, so the TensorRT benchmark would have measured the wrong thing. | `config.py` now reads `EDGE_SOURCE`, `EDGE_DEVICE`, `EDGE_PERSON_WEIGHTS`, `EDGE_FIRE_WEIGHTS` and `EDGE_SERVER_URL` | `config.py` |
| 2 | The Jetson CSI camera needs a GStreamer pipeline string, but every string source was treated as a **video file**, which gave wrong timing and frame skipping. | `EDGE_SOURCE=csi` builds an `nvarguscamerasrc` pipeline, opened with `CAP_GSTREAMER`. Camera settings are `CSI_*` in `config.py`. | `frame_source.py`, `config.py` |
| 3 | The ground station only listened on `127.0.0.1`, so the Jetson could not reach it. | Uses `GS_HOST` / `GS_PORT` (e.g. `GS_HOST=0.0.0.0`) | `ground_station/app.py` |
| 4 | Jetson notes were missing. | README: table of environment variables, power-supply note, YOLO26-on-JetPack-4 check, CSI camera instructions | `README.md` |

### Round 2: making the alert link reliable

| # | Problem on `main` | Fix | Files |
|---|---|---|---|
| 5 | Alerts were only sent **after the video ended**. A live camera never ends, so in a real flight **no alert would ever reach the ground station**. Ctrl+C also skipped the final send. | Sends buffered alerts every `FORWARD_INTERVAL_SEC` (5 s) during the run. Ctrl+C stops cleanly and does a final send. | `run_pipeline.py`, `config.py` |
| 6 | When the link was down, each send attempt could freeze the frame loop for up to 3 s. | Connect timeout is now `FORWARD_CONNECT_TIMEOUT` (1 s) | `alert_store.py`, `config.py` |
| 7 | One missing snapshot file crashed forwarding, and **every later alert stayed stuck**. | Sends the alert without the image and logs a warning | `alert_store.py` |
| 8 | If an alert arrived but the reply was lost, the drone resent it and the ground station showed it **twice**. | The drone sends its `alert_id`. The station ignores repeats it has already seen and still replies 200. | `alert_store.py`, `ground_station/app.py` |
| 9 | `check_fire_model.py` could only test one hardcoded video. | Takes an optional video path: `python check_fire_model.py my.mp4` | `check_fire_model.py` |

### New settings

| Variable / setting | Default | Meaning |
|---|---|---|
| `EDGE_SOURCE` | `data/mixed_test.mp4` | video path, camera index (`0`), `csi`, or a GStreamer pipeline |
| `EDGE_DEVICE` | `cpu` | `0` = Jetson GPU |
| `EDGE_PERSON_WEIGHTS` / `EDGE_FIRE_WEIGHTS` | `weights/*.pt` | can point to `.engine` or `.onnx` files |
| `EDGE_SERVER_URL` | `http://localhost:5000/alert` | ground-station address |
| `GS_HOST` / `GS_PORT` | `127.0.0.1` / `5000` | ground-station bind address |
| `FORWARD_INTERVAL_SEC` | `5` | how often alerts are sent during a run |
| `FORWARD_CONNECT_TIMEOUT` | `1.0` | seconds before giving up on a dead link |
| `CSI_SENSOR_ID`, `CSI_CAPTURE_*`, `CSI_FLIP` | `0`, 1280x720@30, `0` | CSI camera settings |

---

## 4. How the changes were tested

These checks were run on a laptop (macOS), **not on the Jetson**:

- **Settings:** with no variables set, defaults are unchanged. With variables set, they are picked up (e.g. `EDGE_DEVICE=0` gives `'0'`, and an `.engine` path is used).
- **Camera source:** `csi` builds the right pipeline and opens it with GStreamer. Integers and real files are handled as before. (OpenCV was stubbed for this check.)
- **Alert link, end to end against a real ground-station server:**
  - Server offline: all 3 alerts stay buffered and the attempt takes 0.3 s.
  - Server online with one snapshot deleted: all 3 alerts arrive, and the one without an image still shows up.
  - Resending every alert to simulate a lost reply: the station still shows 3 alerts, not 6.
  - The station lists alerts in the order person, fire, smoke.
- **Full pipeline on a synthetic video with a stubbed YOLO:** it tried to send every frame during the run, raised the fire alert once (cooldown works), kept the alert buffered with no server, and did not stall.

**Not tested yet:** real YOLO models, a real camera, Ctrl+C on a live camera, anything on the Jetson.

---

## 5. Running on the Jetson Nano

Power it from a **5V 4A barrel jack with the J48 jumper fitted**, then:

```bash
sudo nvpmodel -m 0 && sudo jetson_clocks
sudo docker run -it --ipc=host --runtime=nvidia -v $(pwd):/work -w /work -p 5000:5000 \
     -v /tmp/argus_socket:/tmp/argus_socket \
     ultralytics/ultralytics:latest-jetson-jetpack4
pip install flask requests

# 1. Does the fire model (YOLO26) load on JetPack 4?  <- check this first
EDGE_DEVICE=0 python check_fire_model.py

# 2. PyTorch benchmark on the GPU
EDGE_DEVICE=0 python benchmark.py

# 3. TensorRT
python export_trt.py
EDGE_DEVICE=0 EDGE_PERSON_WEIGHTS=weights/yolov8n.engine \
EDGE_FIRE_WEIGHTS=weights/fire_smoke.engine python benchmark.py

# 4. Live run with alerts sent to a laptop
#    laptop:  GS_HOST=0.0.0.0 python ground_station/app.py
EDGE_DEVICE=0 EDGE_SOURCE=csi EDGE_SERVER_URL=http://<laptop-ip>:5000/alert python run_pipeline.py
```

Copy these to the board as well, since they are not in git: `weights/*.pt`, `data/mixed_test.mp4`, `data/mixed_test_labels.json`.

---

## 6. Still open

| Priority | Item | Why it matters |
|---|---|---|
| High | **Check that YOLO26 loads on JetPack 4.** If it does not, export to ONNX on the laptop. | The fire model may not run on the Nano at all. |
| High | **Jetson benchmark and power numbers** (`tegrastats`) | This is the main result of the project. |
| High | **Stage 1 on a moving drone:** the motion signal assumes a still camera. | Drone movement will keep waking Stage 2 and remove most of the saving. Needs motion compensation or a colour-led gate. |
| Medium | Skip Stage 2 on some frames after a confirmed fire | Saves GPU time and heat while a fire stays in view |
| Medium | Test person detection on aerial footage | The person model is untested on video |
| Medium | Stress-test Stage 1 on orange terrain, sunsets and fast motion | Risk of false triggers |
| Low | The ground-station map needs internet (Leaflet and map tiles) | Offline in the field, the table works but the map is blank |
| Low | Ground-station alerts live in memory | Restarting the station loses the list. Snapshots are kept on disk. |
| Low | Real GPS (e.g. MAVLink from the flight controller) instead of the simulation | Needed for real flights |
