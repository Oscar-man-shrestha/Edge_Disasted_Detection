# Drone Edge: adaptive-compute disaster detection

A drone-mounted edge pipeline that detects fire/smoke and people without internet.
A cheap OpenCV check (Stage 1) runs on every sampled frame; the heavy YOLO models
(Stage 2) run only when Stage 1 flags something. Alerts are tagged with GPS, stored
locally (SQLite), and forwarded to a ground station when a link exists.

camera -> Stage 1 gate -> Stage 2 YOLO -> GPS tag -> SQLite store -> live link -> ground station dashboard

**Start here:** [GUIDE.md](GUIDE.md) is the complete step-by-step guide to building, wiring, connecting and running everything.
Current status, recent changes and open work: see [PROJECT_STATUS.md](PROJECT_STATUS.md).

## Setup (laptop)

    python -m venv venv
    venv\Scripts\activate        # Windows
    pip install -r requirements.txt

Models and videos are NOT in the repo. Put them here:

| File | Source |
|---|---|
| `weights/yolov8n.pt` | Ultralytics YOLOv8n (COCO, class 0 = person) |
| `weights/fire_smoke.pt` | `best.pt` from Hugging Face `seawsurf/fire_yolo` (classes: fire, smoke) |
| `data/test_video.mp4`, `data/calm.mp4` | any aerial fire clip and any calm aerial clip |

Build the mixed test video (calm, then fire) and its ground-truth label file:

    python make_mixed_video.py data\calm.mp4 data\test_video.mp4 data\mixed_test.mp4

Then set `SOURCE = "data/mixed_test.mp4"` in `config.py`.

## Run

| Command | What it does |
|---|---|
| `python -m pytest` | automated tests (no models or video needed) |
| `python test_source.py` | check frame sampling |
| `python test_stage1.py` | Stage 1 gate on the video |
| `python test_stage2.py` | gated pipeline + timing |
| `python check_fire_model.py [video]` | sanity-check the fire model on a few frames |
| `python ground_station\app.py` | ground station dashboard at http://localhost:5000 (the drone finds it automatically) |
| `python ground_station\demo_drone.py` | simulated drone, to demo the dashboard without the Jetson |
| `python ground_station\tiles.py prefetch --bbox ... --zoom 14-18 [--terrain]` | download map (and 3D terrain) tiles for offline use |
| `cd ground_station\web && npm ci && npm run dev` | work on the dashboard UI (React + TypeScript; see GUIDE.md → "Working on the dashboard UI") |
| `python run_pipeline.py` | full pipeline, writes alerts to `data/alerts.db` and sends them |
| `python forward_now.py` | push buffered alerts to the ground station |
| `python benchmark.py [--source v.mp4] [--tag name]` | gated vs. heavy model on every frame (+ energy on Jetson) |
| `python gps_source.py` | print GPS fixes from the configured GPS mode |
| `python power_monitor.py` | Jetson board power reading |

Settings live in `config.py`. These can be overridden by environment variables:

| Variable | Default | Meaning |
|---|---|---|
| `EDGE_SOURCE` | `data/mixed_test.mp4` | video path, USB camera index (`0`), `csi`, a GStreamer pipeline, or an MJPEG URL |
| `EDGE_DEVICE` | `cpu` | `0` = first CUDA GPU (Jetson) |
| `EDGE_PERSON_WEIGHTS` | `weights/yolov8n.pt` | person model (`.pt`, `.engine`, `.onnx`) |
| `EDGE_FIRE_WEIGHTS` | `weights/fire_smoke.pt` | fire/smoke model |
| `EDGE_SERVER_URL` | `auto` | `auto` finds the ground station by its beacon; or `http://host:5000` |
| `EDGE_DRONE_ID` / `EDGE_LINK_KEY` | hostname / none | drone name on the dashboard; shared key (must match `GS_LINK_KEY`) |
| `EDGE_GPS` | `sim` | `sim`, `nmea` (u-blox M8N on serial) or `mavlink` (flight controller) |
| `EDGE_GPS_PORT` / `EDGE_GPS_BAUD` | `/dev/ttyTHS1` / `0` (auto) | serial port for `nmea` |
| `EDGE_MAVLINK_URL` | `/dev/ttyTHS1,57600` | connection for `mavlink` |
| `EDGE_MOTION_COMP` | `1` | Stage 1 camera-motion compensation on/off |
| `EDGE_STAGE2_EVERY_N` | `3` | while a detection is confirmed, run Stage 2 on every Nth triggered frame |
| `EDGE_DB_PATH` | `data/alerts.db` | drone-side alert buffer |
| `GS_HOST` / `GS_PORT` / `GS_DATA_DIR` | `0.0.0.0` / `5000` / `ground_station/received` | ground station (`127.0.0.1` = this laptop only) |
| `GS_LINK_KEY` / `GS_BEACON_TARGETS` | none / `255.255.255.255,10.42.0.255` | shared key the drone must send; where the station announces itself |

## Benchmark (laptop CPU, one test video: 48 calm + 59 fire frames)

| Metric | Result |
|---|---|
| Frames that woke Stage 2 | 57 of 107 (53.3%) |
| Compute time, heavy model on every frame | 8.26 s |
| Compute time, gated pipeline | 4.64 s (43.8% saved) |
| Stage 1 false triggers on calm frames | 0 |
| Fire frames skipped by the gate | 2 of 59 (3-frame confirmation delay) |
| Fire confirmed after onset | 0.96 s |

Caveats: one clip with gentle camera motion; the saving depends on the calm/fire mix;
person detection is not yet tested on video; laptop numbers only.
These numbers were measured before motion compensation and the Stage 2 scheduler were
added; re-run `benchmark.py` for current figures.

## Jetson Nano

Hardware: Jetson Nano Developer Kit B01, Lenovo USB webcam, u-blox NEO-M8N GPS.
Everything (wiring, setup script, Docker, benchmark order, autostart, troubleshooting)
is in **[JETSON.md](JETSON.md)**. Short version:

    jetson/setup_nano.sh                                   # once
    EDGE_DEVICE=0 jetson/run_docker.sh python3 check_fire_model.py data/mixed_test.mp4
    EDGE_DEVICE=0 jetson/run_docker.sh python3 benchmark.py --tag nano_pytorch
    jetson/run_docker.sh python3 export_trt.py
    sudo jetson/install_service.sh                         # start at boot

## TODO
See the "Still open" table in [PROJECT_STATUS.md](PROJECT_STATUS.md).

## Credits and licences
- Fire/smoke model: `seawsurf/fire_yolo` on Hugging Face (YOLO26n fine-tuned on the
  FASDD dataset; CC-BY-4.0). Weights are not redistributed here.
- Ultralytics YOLO is AGPL-3.0. Check the implications before distributing this project.
- Test footage was stock video and is not included.