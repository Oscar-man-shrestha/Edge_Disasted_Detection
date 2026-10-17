from ultralytics import YOLO

for w in ["weights/yolov8n.pt", "weights/fire_smoke.pt"]:
    print("exporting", w)
    YOLO(w).export(format="engine", half=True, imgsz=640, device=0)

