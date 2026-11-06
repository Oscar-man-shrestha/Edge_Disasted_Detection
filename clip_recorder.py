"""Short video clips around alerts, made from the frames the pipeline already samples.

    rec = ClipRecorder()
    for t, frame in ...:
        for alert_id, path, n, fps in rec.push(t, frame):   # finished clips
            store.set_clip(alert_id, path, n, fps)
        ...
        rec.request(alert_id, t)                            # when an alert is made
    rec.flush()                                             # on shutdown

A clip is a folder of JPEGs (000.jpg, 001.jpg, ...) from CLIP_BEFORE_SEC before to
CLIP_AFTER_SEC after the alert. JPEG frames play in any browser and need no video
codec on the Jetson. Safe on the Nano: frames are kept small and already JPEG-encoded
in RAM (~20 frames x ~25 KB), and only the newest CLIP_KEEP clips stay on the SD card.
Python 3.8 compatible.
"""
import os
import shutil
from collections import deque

import cv2

import config


class ClipRecorder:
    def __init__(self, before=None, after=None, width=None, quality=None, clip_dir=None, keep=None):
        self.before = config.CLIP_BEFORE_SEC if before is None else before
        self.after = config.CLIP_AFTER_SEC if after is None else after
        self.width = config.CLIP_WIDTH if width is None else width
        self.quality = config.CLIP_QUALITY if quality is None else quality
        self.clip_dir = config.CLIP_DIR if clip_dir is None else clip_dir
        self.keep = config.CLIP_KEEP if keep is None else keep
        self.buf = deque()            # (t, jpeg bytes), the last before+after+2 seconds
        self.pending = []             # (alert_id, t_alert)
        os.makedirs(self.clip_dir, exist_ok=True)

    def _encode(self, frame):
        h, w = frame.shape[:2]
        if w > self.width:
            frame = cv2.resize(frame, (self.width, int(h * self.width / w)), interpolation=cv2.INTER_AREA)
        ok, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, int(self.quality)])
        return jpg.tobytes() if ok else None

    def push(self, t, frame):
        """Add one sampled frame; returns the clips that are now complete."""
        jpg = self._encode(frame)
        if jpg is not None:
            self.buf.append((t, jpg))
        horizon = t - (self.before + self.after + 2)
        while self.buf and self.buf[0][0] < horizon:
            self.buf.popleft()
        if t < (self.buf[0][0] if self.buf else t):        # clock restarted: start over
            self.buf.clear()
        done = [p for p in self.pending if t >= p[1] + self.after]
        self.pending = [p for p in self.pending if p not in done]
        return [c for c in (self._write(aid, ta) for aid, ta in done) if c]

    def request(self, alert_id, t):
        self.pending.append((alert_id, t))

    def flush(self):
        """Write every pending clip with the frames there are (used on shutdown)."""
        done, self.pending = self.pending, []
        return [c for c in (self._write(aid, ta) for aid, ta in done) if c]

    def _write(self, alert_id, t_alert):
        frames = [(ft, j) for ft, j in self.buf if t_alert - self.before <= ft <= t_alert + self.after]
        if not frames:
            return None
        path = os.path.join(self.clip_dir, str(alert_id))
        shutil.rmtree(path, ignore_errors=True)
        os.makedirs(path)
        for i, (_, jpg) in enumerate(frames):
            with open(os.path.join(path, "%03d.jpg" % i), "wb") as f:
                f.write(jpg)
        span = frames[-1][0] - frames[0][0]
        fps = (len(frames) - 1) / span if span > 0 else 1.0
        self._prune()
        return alert_id, path, len(frames), round(fps, 2)

    def _prune(self):
        ids = sorted((d for d in os.listdir(self.clip_dir) if d.isdigit()), key=int)
        for d in ids[:max(0, len(ids) - self.keep)]:
            shutil.rmtree(os.path.join(self.clip_dir, d), ignore_errors=True)
