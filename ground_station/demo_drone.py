"""Simulated drone for demos and testing the ground station without the Jetson.

Uses the real drone code (link.py, Stage 1 gate, scheduler, AlertStore, GPS sim);
only the camera, YOLO and board sensors are simulated.

    python ground_station/app.py                       # terminal 1
    python ground_station/demo_drone.py                # terminal 2 (finds the station by beacon)
    python ground_station/demo_drone.py --video data/mixed_test.mp4 --station http://localhost:5000
    python ground_station/demo_drone.py --no-gps       # test the "no fix" handling

Scenario (repeats every --cycle seconds): calm flight, then a fire appears at 35 %
of the cycle and stays until 80 %; a person is spotted near the fire at 55 %.
"""
import argparse
import math
import os
import sys
import tempfile
import time

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import config  # noqa: E402


class NoFixGPS:
    def position(self, t=None):
        return float("nan"), float("nan")

    def status(self, t=None):
        return {"mode": "nmea", "fix": False, "lat": None, "lon": None, "alt_m": None,
                "sats": 3, "hdop": 9.9, "speed_mps": None, "course_deg": None, "age_s": None}


class LoopGPS:
    """GPSSim that restarts the flight path when it reaches the end."""

    def __init__(self, sim):
        self.sim = sim
        self.period = sim.total / sim.speed

    def position(self, t):
        return self.sim.position(t % self.period)

    def status(self, t):
        return self.sim.status(t % self.period)


class FakeStats:
    def __init__(self, state):
        self.state = state
        self.t0 = time.time()

    def read(self):
        active = self.state.snapshot()["state"] == "active"
        wob = math.sin((time.time() - self.t0) / 7.0)
        return {"power_mw": round((7200 if active else 4700) + 300 * wob),
                "cpu_temp_c": round(52 + 6 * active + 2 * wob, 1),
                "gpu_temp_c": round(49 + 9 * active + 2 * wob, 1),
                "cpu_load_pct": round(38 + 30 * active + 5 * wob),
                "gpu_load_pct": round(8 + 75 * active),
                "ram_used_mb": 2650 + 250 * active, "ram_total_mb": 3956}


class SyntheticCamera:
    """Textured terrain that drifts like a moving drone; fire/person drawn by scenario."""

    def __init__(self, w=640, h=360, seed=1):
        rng = np.random.default_rng(seed)
        base = rng.integers(0, 255, (h * 3, w * 3), dtype=np.uint8)
        base = cv2.GaussianBlur(base, (0, 0), 6)
        base = cv2.normalize(base, None, 40, 150, cv2.NORM_MINMAX)
        terrain = np.dstack([base * 0.55, base * 0.85, base * 0.6]).astype(np.uint8)  # greenish
        for _ in range(14):                                   # fields / roads for texture
            x, y = rng.integers(0, w * 3 - 120), rng.integers(0, h * 3 - 80)
            cv2.rectangle(terrain, (int(x), int(y)), (int(x + rng.integers(60, 200)),
                          int(y + rng.integers(30, 120))), tuple(int(c) for c in rng.integers(60, 140, 3)), -1)
        self.world, self.w, self.h = terrain, w, h

    def frame(self, t):
        ox = int(200 + 140 * math.sin(t / 9.0))
        oy = int(150 + 90 * math.sin(t / 13.0))
        return self.world[oy:oy + self.h, ox:ox + self.w].copy()


def draw_fire(img, t, x=300, y=150):
    flick = 1 + 0.15 * math.sin(t * 7)
    cv2.ellipse(img, (x, y), (int(70 * flick), int(48 * flick)), 0, 0, 360, (20, 110, 250), -1)
    cv2.ellipse(img, (x, y + 6), (int(38 * flick), int(26 * flick)), 0, 0, 360, (60, 200, 255), -1)
    cv2.circle(img, (x - 50, y - 70), 40, (170, 170, 175), -1)               # smoke puff
    return [x - 70, y - 48, x + 70, y + 48]


def draw_person(img, x=470, y=230):
    cv2.circle(img, (x, y - 26), 8, (40, 40, 40), -1)
    cv2.rectangle(img, (x - 9, y - 18), (x + 9, y + 14), (200, 60, 30), -1)
    return [x - 12, y - 36, x + 12, y + 16]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--station", default="auto", help="'auto' (beacon) or http://host:port")
    ap.add_argument("--video", help="use frames from this video instead of the synthetic camera")
    ap.add_argument("--no-gps", action="store_true", help="simulate a GPS without a fix")
    ap.add_argument("--speed", type=float, default=5.0, help="simulated ground speed, m/s")
    ap.add_argument("--cycle", type=float, default=80.0, help="scenario length in seconds")
    ap.add_argument("--fps", type=float, default=2.0, help="sampled frames per second")
    ap.add_argument("--db", default=os.path.join(tempfile.gettempdir(), "demo_drone", "alerts.db"))
    ap.add_argument("--id", default="demo-drone")
    a = ap.parse_args()

    os.makedirs(os.path.dirname(a.db), exist_ok=True)
    config.DB_PATH = a.db
    config.SNAPSHOT_DIR = os.path.join(os.path.dirname(a.db), "snaps")
    config.DRONE_ID = a.id
    config.FLIGHT_PATH_CSV = os.path.join(ROOT, "data", "flight_path.csv")

    from alert_store import AlertStore
    from gps_sim import GPSSim
    from link import DroneLink, LinkState, StationFinder
    from stage1_gate import Stage1Gate
    from stage2_detector import Stage2Scheduler

    gps = NoFixGPS() if a.no_gps else LoopGPS(GPSSim(config.FLIGHT_PATH_CSV, a.speed))
    state = LinkState()
    finder = StationFinder(fixed_url=None if a.station == "auto" else a.station)
    link = DroneLink(state, gps, finder, stats=FakeStats(state)).start()
    store, gate, sched = AlertStore(), Stage1Gate(), Stage2Scheduler()
    cam = None if a.video else SyntheticCamera()
    cap = cv2.VideoCapture(a.video) if a.video else None
    print("demo drone '%s': station=%s gps=%s db=%s" % (a.id, a.station,
                                                         "no-fix" if a.no_gps else "sim", a.db))
    t0 = time.time()
    try:
        while True:
            t = time.time() - t0
            phase = (t % a.cycle) / a.cycle
            if cap is not None:
                ok, frame = cap.read()
                if not ok:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                frame = cv2.resize(frame, (config.FRAME_WIDTH, config.FRAME_HEIGHT))
            else:
                frame = cam.frame(t)
            dets = []
            if 0.35 <= phase < 0.80:
                box = draw_fire(frame, t) if cap is None else [250, 110, 390, 230]
                dets.append({"type": "fire", "conf": round(0.72 + 0.2 * abs(math.sin(t)), 2), "box": box})
                if phase > 0.45:
                    dets.append({"type": "smoke", "conf": 0.55, "box": [box[0] - 40, box[1] - 70, box[0] + 40, box[1]]})
            if 0.55 <= phase < 0.62:
                dets.append({"type": "person", "conf": 0.81,
                             "box": draw_person(frame) if cap is None else [450, 190, 480, 250]})

            r = gate.check(frame)
            trigger = r["trigger"] or bool(dets)            # the synthetic fire may be too small for the gate
            if sched.should_run(trigger):
                time.sleep(0.12)                             # pretend YOLO time
                sched.update(dets)
                state.frame(frame, r, ran_stage2=True, stage2_ms=120.0, t=t, skipped=sched.skipped)
                state.detections(dets, time.time())
                lat, lon = gps.position(t)
                for d in dets:
                    aid = store.maybe_add(d, frame, t, lat, lon)
                    if aid:
                        print("ALERT #%d %s %.2f" % (aid, d["type"], d["conf"]))
            else:
                state.frame(frame, r, ran_stage2=False, t=t, skipped=sched.skipped)
            time.sleep(max(0.0, 1.0 / a.fps - (time.time() - t0 - t)))
    except KeyboardInterrupt:
        pass
    finally:
        link.stop()
        print("demo drone stopped; alerts sent:", link.alerts_sent)


if __name__ == "__main__":
    main()
