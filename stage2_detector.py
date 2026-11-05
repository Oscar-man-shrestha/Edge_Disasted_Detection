import os
import time
import config


class Stage2Detector:
    """Heavy check. Only call this when Stage 1 triggers (and the scheduler agrees).

    Weights can be .pt (PyTorch), .engine (TensorRT, built on the Jetson) or .onnx.
    """

    def __init__(self):
        import numpy as np
        if not hasattr(np, "bool"):           # TensorRT 8.2 (JetPack 4) still uses np.bool,
            np.bool = bool                    # removed in numpy 1.24
        from ultralytics import YOLO          # imported here so tests can run without it
        self.person_model = YOLO(config.PERSON_WEIGHTS, task="detect")
        self.fire_model = None
        if os.path.exists(config.FIRE_WEIGHTS):
            self.fire_model = YOLO(config.FIRE_WEIGHTS, task="detect")
        else:
            print(f"[stage2] {config.FIRE_WEIGHTS} not found -> person detection only")

    def _run(self, model, frame, classes=None):
        r = model.predict(frame, conf=config.CONF_THRESHOLD, device=config.DEVICE,
                          imgsz=config.IMG_SIZE, classes=classes, verbose=False)[0]
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


class Stage2Scheduler:
    """Decides whether a Stage-1-triggered frame actually goes to Stage 2.

    - Not confirmed yet: run on every triggered frame (fastest first detection).
    - Once Stage 2 has found something: run only every Nth triggered frame while
      detections keep coming. Alerts have a cooldown anyway, so the skipped frames
      would mostly produce duplicates.
    - Stage 2 finds nothing, or Stage 1 stops triggering: back to every frame.
    """

    def __init__(self, every_n=None):
        self.every_n = max(1, every_n if every_n is not None
                           else config.STAGE2_EVERY_N_WHILE_CONFIRMED)
        self.confirmed = False
        self.count = 0
        self.skipped = 0

    def should_run(self, trigger):
        if not trigger:
            self.confirmed = False
            self.count = 0
            return False
        if not self.confirmed:
            return True
        self.count += 1
        run = self.count % self.every_n == 0
        if not run:
            self.skipped += 1
        return run

    def update(self, dets):
        """Call after every Stage 2 run with its detections."""
        if dets:
            self.confirmed = True
        else:
            self.confirmed = False
            self.count = 0
