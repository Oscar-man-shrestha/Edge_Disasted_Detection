import os
import time
from ultralytics import YOLO
import config


class Stage2Detector:
    """Heavy check. Only call this when Stage 1 triggers."""

    def __init__(self):
        self.person_model = YOLO(config.PERSON_WEIGHTS)
        self.fire_model = None
        if os.path.exists(config.FIRE_WEIGHTS):
            self.fire_model = YOLO(config.FIRE_WEIGHTS)
        else:
            print(f"[stage2] {config.FIRE_WEIGHTS} not found -> person detection only")

    def _run(self, model, frame, classes=None):
        r = model.predict(frame, conf=config.CONF_THRESHOLD, device=config.DEVICE,
                          classes=classes, verbose=False)[0]
        out = []
        for box in r.boxes:
            out.append({
                "type": r.names[int(box.cls[0])].lower(),
                "conf": float(box.conf[0]),
                "box": [float(v) for v in box.xyxy[0]],
            })
        return out

    def detect(self, frame):
        t0 = time.perf_counter()
        dets = self._run(self.person_model, frame, classes=[0])   # COCO class 0 = person
        if self.fire_model is not None:
            dets += self._run(self.fire_model, frame)
        ms = (time.perf_counter() - t0) * 1000
        return dets, ms