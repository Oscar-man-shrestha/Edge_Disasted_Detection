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
    - Safety-net scan (scan_every seconds, 0 = off): run Stage 2 anyway when it has not
      run for that long. The motion gate cannot see things that do not move or are far
      away (a person standing still, a small distant fire); the scan still looks.
    """

    def __init__(self, every_n=None, scan_every=None):
        self.every_n = max(1, every_n if every_n is not None
                           else config.STAGE2_EVERY_N_WHILE_CONFIRMED)
        self.scan_every = config.SCAN_EVERY_SEC if scan_every is None else scan_every
        self.confirmed = False
        self.count = 0
        self.skipped = 0
        self.scans = 0                     # Stage 2 runs started by the scan, not the gate
        self.last_run_t = None

    def _ran(self, t, run):
        if run and t is not None:
            self.last_run_t = t
        return run

    def should_run(self, trigger, t=None):
        if not trigger:
            self.confirmed = False
            self.count = 0
            due = (self.scan_every and t is not None and
                   (self.last_run_t is None or t - self.last_run_t >= self.scan_every - 1e-9))
            if due:
                self.scans += 1
            return self._ran(t, bool(due))
        if not self.confirmed:
            return self._ran(t, True)
        self.count += 1
        run = self.count % self.every_n == 0
        if not run:
            self.skipped += 1
        return self._ran(t, run)

    def update(self, dets):
        """Call after every Stage 2 run with its detections."""
        if dets:
            self.confirmed = True
        else:
            self.confirmed = False
            self.count = 0
