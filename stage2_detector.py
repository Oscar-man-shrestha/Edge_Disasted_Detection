import os
import time
import config


def tile_boxes(width, height, n, overlap=0.2):
    """n side-by-side tiles (x0, y0, x1, y1) covering a frame, neighbours overlapping by
    `overlap` of a tile, so someone standing on a seam is whole in at least one tile."""
    if n < 2:
        return []
    tw = int(round(width / (n - (n - 1) * overlap)))
    step = (width - tw) / (n - 1)
    return [(int(round(i * step)), 0, int(round(i * step)) + tw, height) for i in range(n)]


def _iou_and_cover(a, b):
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    area = lambda r: max(0.0, r[2] - r[0]) * max(0.0, r[3] - r[1])
    ua = area(a) + area(b) - inter
    return (inter / ua if ua else 0.0), (inter / min(area(a), area(b)) if min(area(a), area(b)) else 0.0)


def merge_dets(dets, iou=0.5, cover=0.8):
    """One box per object when the whole frame and the tiles found it more than once:
    per type, keep the most confident box and drop boxes that overlap it (IoU) or lie
    mostly inside it (a tile only saw part of the person)."""
    def duplicate(k, d):
        if k["type"] != d["type"]:
            return False
        overlap, inside = _iou_and_cover(k["box"], d["box"])
        return overlap > iou or inside > cover

    kept = []
    for d in sorted(dets, key=lambda x: -x["conf"]):
        if not any(duplicate(k, d) for k in kept):
            kept.append(d)
    return kept


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

    def _tiled(self, model, frame, full, classes=None):
        """Detections in full-resolution tiles, boxes mapped back to `frame` pixels. Something
        far away is ~2x bigger in a tile than in the downscaled frame: about 1.8x the range."""
        sx, sy = frame.shape[1] / full.shape[1], frame.shape[0] / full.shape[0]
        out = []
        for x0, y0, x1, y1 in tile_boxes(full.shape[1], full.shape[0], config.TILES, config.TILE_OVERLAP):
            for d in self._run(model, full[y0:y1, x0:x1], classes=classes):
                b = d["box"]
                d["box"] = [(b[0] + x0) * sx, (b[1] + y0) * sy, (b[2] + x0) * sx, (b[3] + y0) * sy]
                out.append(d)
        return out

    def detect(self, frame, full=None):
        """frame: the downscaled pipeline frame. full: the camera frame at full resolution;
        with EDGE_TILES >= 2 people (and fire/smoke with EDGE_TILE_FIRE) are also searched in
        tiles of it (longer range)."""
        t0 = time.perf_counter()
        tiled = config.TILES >= 2 and full is not None and full.shape[1] > frame.shape[1]
        dets = self._run(self.person_model, frame, classes=[0])   # COCO class 0 = person
        if tiled:
            dets = merge_dets(dets + self._tiled(self.person_model, frame, full, classes=[0]))
        if self.fire_model is not None:
            fire = self._run(self.fire_model, frame)
            if tiled and config.TILE_FIRE:
                fire = merge_dets(fire + self._tiled(self.fire_model, frame, full))
            dets += fire
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
