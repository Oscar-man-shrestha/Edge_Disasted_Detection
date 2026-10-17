import cv2
from ultralytics import YOLO
import config

model = YOLO(config.FIRE_WEIGHTS)
print("classes:", model.names)

cap = cv2.VideoCapture("data/test_video.mp4")
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