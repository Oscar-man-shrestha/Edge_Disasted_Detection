"""Build TensorRT FP16 engines ON THE JETSON (engines are device-specific, never commit them).

    jetson/run_docker.sh python3 export_trt.py
    jetson/run_docker.sh python3 export_trt.py weights/fire_smoke.pt     # one model

Then run with EDGE_PERSON_WEIGHTS=weights/yolov8n.engine EDGE_FIRE_WEIGHTS=weights/fire_smoke.engine.
Takes several minutes per model on a Nano; enable swap first (jetson/setup_nano.sh).
"""
import os
import sys
from ultralytics import YOLO
import config

weights = sys.argv[1:] or ["weights/yolov8n.pt", "weights/fire_smoke.pt"]
for w in weights:
    if not os.path.exists(w):
        print("skip (not found):", w)
        continue
    print("exporting", w, "-> TensorRT FP16, imgsz", config.IMG_SIZE)
    out = YOLO(w).export(format="engine", half=True, imgsz=config.IMG_SIZE, device=0,
                         workspace=1)          # GB; the Nano only has 4 GB shared memory
    print("  wrote", out)
