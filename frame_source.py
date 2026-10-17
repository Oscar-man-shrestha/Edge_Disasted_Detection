import time
import cv2
import config


class FrameSource:
    """Yields (frame_index, timestamp, frame) at SAMPLE_INTERVAL_SEC spacing."""

    def __init__(self, source=config.SOURCE, interval=config.SAMPLE_INTERVAL_SEC):
        self.cap = cv2.VideoCapture(source)
        if not self.cap.isOpened():
            raise RuntimeError(f"Could not open source: {source}")
        self.is_file = isinstance(source, str)
        self.interval = interval
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
        # For video files, skip frames to match the interval; for cameras, use the clock.
        self.skip = max(1, int(self.fps * interval))
        self.frame_index = 0
        self._last_time = 0.0

    def frames(self):
        while True:
            ok, frame = self.cap.read()
            if not ok:
                break
            self.frame_index += 1

            if self.is_file:
                if (self.frame_index - 1) % self.skip != 0:
                    continue
                ts = (self.frame_index - 1) / self.fps   # video time in seconds
            else:
                now = time.time()
                if now - self._last_time < self.interval:
                    continue
                self._last_time = now
                ts = now

            frame = cv2.resize(frame, (config.FRAME_WIDTH, config.FRAME_HEIGHT))
            yield self.frame_index, ts, frame

        self.cap.release()