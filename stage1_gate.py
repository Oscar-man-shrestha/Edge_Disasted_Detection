import time
from collections import deque
import cv2
import numpy as np
import config


class Stage1Gate:
    """Cheap per-frame check. Call check(frame) once per sampled frame.

    Two signals, either one flags the frame:
      1. fire-coloured pixels (HSV range)
      2. change versus the previous sampled frame. With MOTION_COMPENSATION the
         previous frame is first aligned to the current one (sparse optical flow
         + similarity transform), so panning/drifting of the drone is not counted
         as change; only things that move relative to the ground are.
    """

    def __init__(self, motion_compensation=None):
        self.prev_gray = None
        # Compare against the frame ~MOTION_BASELINE_SEC ago, not simply the previous one,
        # so motion sensitivity stays the same when frames are sampled faster.
        n = max(1, int(round(config.MOTION_BASELINE_SEC / config.SAMPLE_INTERVAL_SEC)))
        self._history = deque(maxlen=n)
        self.streak = 0
        self.lower = np.array(config.FIRE_HSV_LOWER)
        self.upper = np.array(config.FIRE_HSV_UPPER)
        self.motion_comp = (config.MOTION_COMPENSATION if motion_compensation is None
                            else motion_compensation)

    def _estimate_motion(self, prev, cur):
        """Similarity transform mapping prev -> cur, estimated at half resolution.
        Returns a 2x3 matrix in full-resolution pixels, or None if unreliable."""
        p = cv2.resize(prev, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
        c = cv2.resize(cur, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
        pts = cv2.goodFeaturesToTrack(p, maxCorners=100, qualityLevel=0.01, minDistance=10)
        if pts is None or len(pts) < config.MOTION_MIN_FEATURES:
            return None
        nxt, st, _ = cv2.calcOpticalFlowPyrLK(p, c, pts, None, winSize=(15, 15), maxLevel=3)
        if nxt is None:
            return None
        good = st.reshape(-1) == 1
        if good.sum() < config.MOTION_MIN_FEATURES:
            return None
        m, inliers = cv2.estimateAffinePartial2D(pts[good], nxt[good], method=cv2.RANSAC,
                                                 ransacReprojThreshold=2.0)
        if m is None or inliers is None or inliers.sum() < config.MOTION_MIN_FEATURES:
            return None
        m = m.copy()
        m[:, 2] *= 2.0                       # translation back to full resolution
        return m

    def _diff_fraction(self, gray):
        if self.prev_gray is None:
            return 0.0, False
        prev = self.prev_gray
        valid = None
        aligned = False
        if self.motion_comp:
            m = self._estimate_motion(prev, gray)
            if m is not None:
                h, w = gray.shape
                prev = cv2.warpAffine(prev, m, (w, h), flags=cv2.INTER_LINEAR)
                # pixels that came from outside the old frame are not comparable
                valid = cv2.warpAffine(np.full((h, w), 255, np.uint8), m, (w, h),
                                       flags=cv2.INTER_NEAREST)
                valid = cv2.erode(valid, np.ones((5, 5), np.uint8)) > 0
                aligned = True
        changed = cv2.absdiff(gray, prev) > config.DIFF_PIXEL_THRESHOLD
        if valid is None:
            return np.count_nonzero(changed) / changed.size, aligned
        n_valid = np.count_nonzero(valid)
        if n_valid < 0.25 * valid.size:      # mostly new view: too little overlap to judge
            return 0.0, aligned
        return np.count_nonzero(changed & valid) / n_valid, aligned

    def check(self, frame):
        t0 = time.perf_counter()
        blur = cv2.GaussianBlur(frame, (5, 5), 0)

        # Signal 1: fire-colored pixels
        hsv = cv2.cvtColor(blur, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self.lower, self.upper)
        fire_frac = cv2.countNonZero(mask) / mask.size

        # Signal 2: change vs previous sampled frame (motion-compensated if enabled)
        gray = cv2.cvtColor(blur, cv2.COLOR_BGR2GRAY)
        diff_frac, aligned = self._diff_fraction(gray)
        self._history.append(gray)
        self.prev_gray = self._history[0]

        flagged = (fire_frac >= config.FIRE_PIXEL_FRACTION) or (diff_frac >= config.DIFF_FRACTION)
        self.streak = self.streak + 1 if flagged else 0
        trigger = self.streak >= config.CONSECUTIVE_FLAGS_NEEDED

        return {
            "fire_frac": fire_frac,
            "diff_frac": diff_frac,
            "aligned": aligned,          # True = camera motion was compensated
            "flagged": flagged,
            "streak": self.streak,
            "trigger": trigger,          # True = wake up Stage 2
            "ms": (time.perf_counter() - t0) * 1000,
        }
