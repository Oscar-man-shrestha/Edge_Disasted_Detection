"""Gated pipeline vs. heavy model on every frame, with energy on the Jetson.

    python benchmark.py                                  # uses config.SOURCE
    python benchmark.py --source data/x.mp4 --labels data/x_labels.json --tag nano_trt

Results go to data/benchmark_<tag>.json, so runs with different devices/weights
do not overwrite each other. The default tag is built from device + weight type.
"""
import argparse
import json
import os
import platform

import config
from frame_source import FrameSource
from power_monitor import PowerMonitor
from stage1_gate import Stage1Gate
from stage2_detector import Stage2Detector, Stage2Scheduler

ap = argparse.ArgumentParser()
ap.add_argument("--source", default=config.SOURCE)
ap.add_argument("--labels", default=None,
                help="label json from make_mixed_video.py (default: <source>_labels.json)")
ap.add_argument("--tag", default=None)
args = ap.parse_args()

if not isinstance(args.source, str) or not os.path.isfile(args.source):
    raise SystemExit("benchmark needs a video file (--source), not a live camera")
labels_path = args.labels or args.source.rsplit(".", 1)[0] + "_labels.json"
labels = json.load(open(labels_path))
fire_start = labels["fire_start_sec"]
weights_kind = os.path.splitext(config.PERSON_WEIGHTS)[1].lstrip(".")
tag = args.tag or "%s_%s" % ("gpu" if config.DEVICE != "cpu" else "cpu", weights_kind)

frames = [(ts, f) for _, ts, f in FrameSource(args.source).frames()]
det = Stage2Detector()
for _ in range(3):
    det.detect(frames[0][1])                  # warm-up (TensorRT/CUDA init), not timed
pm = PowerMonitor()
print("power source:", pm.source or "none")

# (a) baseline: heavy model on every frame
base = []
with pm.measure() as e_base:
    for ts, f in frames:
        dets, ms = det.detect(f)
        base.append({"ts": ts, "ms": ms, "hit": len(dets) > 0})

# (b) gated pipeline: Stage 1 on every frame, Stage 2 when triggered and scheduled
gate, sched = Stage1Gate(), Stage2Scheduler()
gated = []
with pm.measure() as e_gated:
    for ts, f in frames:
        r = gate.check(f)
        ms2, hit, ran = 0.0, False, False
        if sched.should_run(r["trigger"]):
            dets, ms2 = det.detect(f)
            sched.update(dets)
            hit, ran = len(dets) > 0, True
        gated.append({"ts": ts, "ms1": r["ms"], "trigger": r["trigger"], "ran": ran,
                      "ms2": ms2, "hit": hit})

# ---- metrics ----
n = len(frames)
ran = sum(g["ran"] for g in gated)
t_base = sum(b["ms"] for b in base) / 1000
t_gated = (sum(g["ms1"] for g in gated) + sum(g["ms2"] for g in gated)) / 1000

calm = [i for i, (ts, _) in enumerate(frames) if ts < fire_start]
fire = [i for i, (ts, _) in enumerate(frames) if ts >= fire_start]

fire_base_hits = [i for i in fire if base[i]["hit"]]
gate_missed = [i for i in fire_base_hits if not gated[i]["trigger"]]
first_base = min((base[i]["ts"] for i in fire_base_hits), default=None)
first_gated = min((g["ts"] for g in gated if g["hit"]), default=None)


def r2(x):
    return None if x is None else round(x, 2)


res = {
    "tag": tag, "device": config.DEVICE, "platform": platform.platform(),
    "person_weights": config.PERSON_WEIGHTS, "fire_weights": config.FIRE_WEIGHTS,
    "motion_compensation": config.MOTION_COMPENSATION,
    "stage2_every_n_while_confirmed": sched.every_n,
    "frames": n, "calm_frames": len(calm), "fire_frames": len(fire),
    "stage1_triggers": sum(g["trigger"] for g in gated),
    "stage2_runs": ran, "stage2_pct": round(100 * ran / n, 1),
    "stage2_skipped_while_confirmed": sched.skipped,
    "avg_stage1_ms": r2(sum(g["ms1"] for g in gated) / n),
    "avg_stage2_ms": r2(t_base * 1000 / n),
    "baseline_sec": r2(t_base), "gated_sec": r2(t_gated),
    "saved_pct": round(100 * (1 - t_gated / t_base), 1),
    "calm_false_triggers": sum(gated[i]["trigger"] for i in calm),
    "calm_heavy_model_detections": sum(base[i]["hit"] for i in calm),
    "fire_frames_with_detection_baseline": len(fire_base_hits),
    "fire_frames_missed_by_gate": len(gate_missed),
    "first_detection_baseline_sec": first_base,
    "first_detection_gated_sec": first_gated,
    "detection_delay_sec": (r2(first_gated - first_base)
                            if first_base is not None and first_gated is not None else None),
    "power_source": pm.source,
}
if pm.available:
    res.update({
        "baseline_avg_mw": r2(e_base.avg_mw), "gated_avg_mw": r2(e_gated.avg_mw),
        "baseline_energy_j": r2(e_base.energy_j), "gated_energy_j": r2(e_gated.energy_j),
        "baseline_j_per_frame": r2(e_base.energy_j / n) if e_base.energy_j else None,
        "gated_j_per_frame": r2(e_gated.energy_j / n) if e_gated.energy_j else None,
        "energy_saved_pct": (round(100 * (1 - e_gated.energy_j / e_base.energy_j), 1)
                             if e_base.energy_j and e_gated.energy_j else None),
    })

print("\n=== BENCHMARK ===")
for k, v in res.items():
    print("%-38s: %s" % (k, v))
os.makedirs("data", exist_ok=True)
out = "data/benchmark_%s.json" % tag
with open(out, "w") as f:
    json.dump(res, f, indent=2)
print("\nsaved", out)
