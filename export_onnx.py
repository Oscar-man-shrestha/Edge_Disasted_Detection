"""Fallback when a model will not load on the Jetson's Ultralytics (e.g. YOLO26 on JetPack 4).

Run on the LAPTOP (newer Ultralytics), then copy the .onnx to the board:

    python export_onnx.py                      # both models
    python export_onnx.py weights/fire_smoke.pt
    scp weights/fire_smoke.onnx <user>@<nano-ip>:~/Edge_Disasted_Detection_Project/weights/

On the board: EDGE_FIRE_WEIGHTS=weights/fire_smoke.onnx. opset 12 is accepted by the
TensorRT 8.2 that ships with JetPack 4.6.
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
    print("exporting", w, "-> ONNX opset 12, imgsz", config.IMG_SIZE)
    out = YOLO(w).export(format="onnx", imgsz=config.IMG_SIZE, opset=12, simplify=True)
    print("  wrote", out)
