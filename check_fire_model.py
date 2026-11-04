import sys
import cv2
from ultralytics import YOLO
import config

model = YOLO(config.FIRE_WEIGHTS)
print("classes:", model.names)

# usage: python check_fire_model.py [video]   (default: data/test_video.mp4)
video = sys.argv[1] if len(sys.argv) > 1 else "data/test_video.mp4"
cap = cv2.VideoCapture(video)
if not cap.isOpened():
    raise SystemExit(f"Cannot open {video}")
for sec in [1, 5, 10, 15, 20, 25]:
    cap.set(cv2.CAP_PROP_POS_MSEC, sec * 1000)
    ok, frame = cap.read()
    if not ok:
        continue
    frame = cv2.resize(frame, (config.FRAME_WIDTH, config.FRAME_HEIGHT))
    r = model.predict(frame, conf=0.05, device=config.DEVICE, verbose=False)[0]
    confs = [round(float(b.conf[0]), 2) for b in r.boxes]
    print(f"t={sec:>2}s  detections={len(confs)}  max_conf={max(confs) if confs else 0}")
    cv2.imwrite(f"data/fire_check_{sec}s.jpg", r.plot())
cap.release()
print("saved data/fire_check_*.jpg")