from frame_source import FrameSource
from stage1_gate import Stage1Gate
from stage2_detector import Stage2Detector
from gps_sim import GPSSim
from alert_store import AlertStore

gate, det, gps, store = Stage1Gate(), Stage2Detector(), GPSSim(), AlertStore()

t0 = None
total = ran = 0
for idx, ts, frame in FrameSource().frames():
    t0 = ts if t0 is None else t0
    t = ts - t0
    total += 1

    r = gate.check(frame)
    if not r["trigger"]:
        continue

    ran += 1
    dets, ms = det.detect(frame)
    lat, lon = gps.position(t)

    best = {}                                   # strongest detection per type
    for d in dets:
        if d["type"] not in best or d["conf"] > best[d["type"]]["conf"]:
            best[d["type"]] = d

    for d in best.values():
        alert_id = store.maybe_add(d, frame, t, lat, lon)
        if alert_id:
            print(f"ALERT #{alert_id}  t={t:5.1f}s  {d['type']:<6} conf={d['conf']:.2f}  "
                  f"lat={lat:.6f} lon={lon:.6f}")

sent, buffered = store.forward_pending()
print(f"\nframes: {total} | Stage 2 ran on: {ran} | sent: {sent} | buffered offline: {buffered}")

print("\nid   t(s)  type    conf   lat        lon        sent")
for row in store.db.execute(
        "SELECT id, video_time, type, conf, lat, lon, sent FROM alerts ORDER BY priority, id"):
    print(f"{row[0]:<4} {row[1]:5.1f} {row[2]:<7} {row[3]:.2f}  {row[4]:.6f} {row[5]:.6f} {row[6]}")