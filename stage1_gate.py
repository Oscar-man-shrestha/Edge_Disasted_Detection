import time
import cv2
import numpy as np
import config


class Stage1Gate:
    """Cheap per-frame check. Call check(frame) once per sampled frame."""

    def __init__(self):
        self.prev_gray = None
        self.streak = 0
        self.lower = np.array(config.FIRE_HSV_LOWER)
        self.upper = np.array(config.FIRE_HSV_UPPER)

    def check(self, frame):
        t0 = time.perf_counter()
        blur = cv2.GaussianBlur(frame, (5, 5), 0)

        # Signal 1: fire-colored pixels
        hsv = cv2.cvtColor(blur, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self.lower, self.upper)
        fire_frac = cv2.countNonZero(mask) / mask.size

        # Signal 2: change vs previous sampled frame
        gray = cv2.cvtColor(blur, cv2.COLOR_BGR2GRAY)
        if self.prev_gray is None:
            diff_frac = 0.0
        else:
            diff = cv2.absdiff(gray, self.prev_gray)
            diff_frac = np.count_nonzero(diff > config.DIFF_PIXEL_THRESHOLD) / diff.size
        self.prev_gray = gray

        flagged = (fire_frac >= config.FIRE_PIXEL_FRACTION) or (diff_frac >= config.DIFF_FRACTION)
        self.streak = self.streak + 1 if flagged else 0
        trigger = self.streak >= config.CONSECUTIVE_FLAGS_NEEDED

        return {
            "fire_frac": fire_frac,
            "diff_frac": diff_frac,
            "flagged": flagged,
            "streak": self.streak,
            "trigger": trigger,          # True = wake up Stage 2
            "ms": (time.perf_counter() - t0) * 1000,
        }