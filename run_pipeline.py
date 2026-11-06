"""Full drone pipeline: camera -> Stage 1 gate -> Stage 2 YOLO -> GPS-tagged alerts.

Alerts, telemetry and camera previews go to the ground station from a background
thread (link.py). By default the station is found automatically (EDGE_SERVER_URL=auto).
"""
import signal
import time

import numpy as np

import config
from alert_store import AlertStore
from frame_source import FrameSource
from gps_source import make_gps
from link import DroneLink, LinkState, StationFinder
from stage1_gate import Stage1Gate
from stage2_detector import Stage2Detector, Stage2Scheduler
from system_stats import SystemStats

gate, det, gps, store = Stage1Gate(), Stage2Detector(), make_gps(), AlertStore()
# Warm-up: TensorRT/CUDA allocate on the first inference (several seconds on a Nano);
# do it now so the first real fire or person is not delayed.
_t0 = time.time()
det.detect(np.zeros((config.FRAME_HEIGHT, config.FRAME_WIDTH, 3), np.uint8))
print("[stage2] models ready (warm-up %.1f s)" % (time.time() - _t0))
sched = Stage2Scheduler()
state = LinkState()
finder = StationFinder(fixed_url=None if config.SERVER_URL == "auto" else config.SERVER_URL)
link = DroneLink(state, gps, finder, stats=SystemStats()).start()
print("[link] station:", config.SERVER_URL if config.SERVER_URL != "auto"
      else "auto (waiting for the ground station beacon on UDP %d)" % config.DISCOVERY_PORT)


def _on_sigterm(signum, frame):
    raise KeyboardInterrupt          # systemd/docker stop -> same clean shutdown as Ctrl+C


signal.signal(signal.SIGTERM, _on_sigterm)

t0 = None
total = ran = 0
try:
    for idx, ts, frame in FrameSource().frames():
        t0 = ts if t0 is None else t0
        t = ts - t0
        total += 1

        r = gate.check(frame)
        if not sched.should_run(r["trigger"]):
            state.frame(frame, r, ran_stage2=False, t=t, skipped=sched.skipped)
            continue

        ran += 1
        dets, ms = det.detect(frame)
        sched.update(dets)
        state.frame(frame, r, ran_stage2=True, stage2_ms=ms, t=t, skipped=sched.skipped)
        state.detections(dets, time.time())
        lat, lon = gps.position(t)

        best = {}                                   # strongest detection per type
        for d in dets:
            if d["type"] not in best or d["conf"] > best[d["type"]]["conf"]:
                best[d["type"]] = d

        for d in best.values():
            alert_id = store.maybe_add(d, frame, t, lat, lon)
            if alert_id:
                print(f"ALERT #{alert_id}  t={t:5.1f}s  {d['type']:<6} conf={d['conf']:.2f}  "
                      f"lat={lat:.6f} lon={lon:.6f}")   # nan = no GPS fix yet
except KeyboardInterrupt:
    print("\n[stop] stopping, flushing alerts")
finally:
    link.stop()

counts = store.counts()
print(f"\nframes: {total} | Stage 2 ran on: {ran} | skipped while confirmed: {sched.skipped} "
      f"| sent: {counts['sent']} | still buffered offline: {counts['buffered']}")

print("\nid   t(s)  type    conf   lat        lon        sent")
for row in store.db.execute(
        "SELECT id, video_time, type, conf, lat, lon, sent FROM alerts ORDER BY priority, id"):
    lat = "      none" if row[4] is None else f"{row[4]:.6f}"
    lon = "      none" if row[5] is None else f"{row[5]:.6f}"
    print(f"{row[0]:<4} {row[1]:5.1f} {row[2]:<7} {row[3]:.2f}  {lat} {lon} {row[6]}")
