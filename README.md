# Drone Edge: adaptive-compute disaster detection

A drone-mounted edge pipeline that detects fire/smoke and people without internet.
A cheap OpenCV check (Stage 1) runs on every sampled frame; the heavy YOLO models
(Stage 2) run only when Stage 1 flags something. Alerts are tagged with GPS, stored
locally (SQLite), and forwarded to a ground station when a link exists.

camera -> Stage 1 gate -> Stage 2 YOLO -> GPS tag -> SQLite store -> Flask ground station

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
| `python test_source.py` | check frame sampling |
| `python test_stage1.py` | Stage 1 gate on the video |
| `python test_stage2.py` | gated pipeline + timing |
| `python check_fire_model.py` | sanity-check the fire model on a few frames |
| `python ground_station\app.py` | ground station at http://localhost:5000 |
| `python run_pipeline.py` | full pipeline, writes alerts to `data/alerts.db` |
| `python forward_now.py` | push buffered alerts to the ground station |
| `python benchmark.py` | gated vs. heavy-model-on-every-frame benchmark |

Settings live in `config.py`. These can be overridden by environment variables:
`EDGE_DEVICE`, `EDGE_PERSON_WEIGHTS`, `EDGE_FIRE_WEIGHTS`, `EDGE_SERVER_URL`, `GS_HOST`.

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

## Jetson Nano (JetPack 4.6): UNTESTED until the board arrives

Ultralytics supports the original Nano only through Docker on JetPack 4.

1. Max performance: `sudo nvpmodel -m 0 && sudo jetson_clocks`
2. `sudo docker pull ultralytics/ultralytics:latest-jetson-jetpack4`
3. Start it with the repo mounted:
   `sudo docker run -it --ipc=host --runtime=nvidia -v $(pwd):/work -w /work -p 5000:5000 ultralytics/ultralytics:latest-jetson-jetpack4`
4. Inside the container: `pip install flask requests`, copy the weights into `weights/`.
5. Check both models load and run: `EDGE_DEVICE=0 python check_fire_model.py`
6. Benchmark in PyTorch: `EDGE_DEVICE=0 python benchmark.py`, then rename
   `data/benchmark_results.json` so the next run does not overwrite it.
7. Export TensorRT engines on the board: `python export_trt.py`
   (engines are device-specific, never commit them), then re-run the benchmark with
   `EDGE_PERSON_WEIGHTS=weights/yolov8n.engine EDGE_FIRE_WEIGHTS=weights/fire_smoke.engine`.
8. Power: `sudo tegrastats --interval 1000 --logfile power.log` during a run
   (look for the input-power field) to compare energy, not just compute time.
9. If the model will not load on JetPack 4: `YOLO(...).export(format="onnx")` on the laptop
   and test the ONNX file on the board.

To send alerts to a laptop ground station, start it with `GS_HOST=0.0.0.0` and set
`EDGE_SERVER_URL=http://<laptop-ip>:5000/alert` on the Jetson.

## TODO
- Stress-test Stage 1: fast camera motion, orange/red terrain, sunsets
- Test person detection on aerial footage
- Skip Stage 2 on some frames after a confirmed fire
- Jetson benchmark and power numbers

## Credits and licences
- Fire/smoke model: `seawsurf/fire_yolo` on Hugging Face (YOLO26n fine-tuned on the
  FASDD dataset; CC-BY-4.0). Weights are not redistributed here.
- Ultralytics YOLO is AGPL-3.0. Check the implications before distributing this project.
- Test footage was stock video and is not included.