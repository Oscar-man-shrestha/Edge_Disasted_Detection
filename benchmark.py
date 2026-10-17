import json
import platform
import config
from frame_source import FrameSource
from stage1_gate import Stage1Gate
from stage2_detector import Stage2Detector

labels = json.load(open("data/mixed_test_labels.json"))
fire_start = labels["fire_start_sec"]

frames = [(ts, f) for _, ts, f in FrameSource().frames()]
det = Stage2Detector()
det.detect(frames[0][1])                      # warm-up, not timed

# (a) baseline: heavy model on every frame
base = []
for ts, f in frames:
    dets, ms = det.detect(f)
    base.append({"ts": ts, "ms": ms, "hit": len(dets) > 0})

# (b) gated pipeline
gate = Stage1Gate()
gated = []
for ts, f in frames:
    r = gate.check(f)
    ms2, hit = 0.0, False
    if r["trigger"]:
        dets, ms2 = det.detect(f)
        hit = len(dets) > 0
    gated.append({"ts": ts, "ms1": r["ms"], "ran": r["trigger"], "ms2": ms2, "hit": hit})

# ---- metrics ----
n = len(frames)
ran = sum(g["ran"] for g in gated)
t_base = sum(b["ms"] for b in base) / 1000
t_gated = (sum(g["ms1"] for g in gated) + sum(g["ms2"] for g in gated)) / 1000

calm = [i for i, (ts, _) in enumerate(frames) if ts < fire_start]
fire = [i for i, (ts, _) in enumerate(frames) if ts >= fire_start]

calm_model_hits = sum(base[i]["hit"] for i in calm)       # heavy-model detections on calm frames
calm_triggers = sum(gated[i]["ran"] for i in calm)        # Stage 1 false alarms
fire_base_hits = [i for i in fire if base[i]["hit"]]
missed = [i for i in fire_base_hits if not gated[i]["hit"]]
first_base = min((base[i]["ts"] for i in fire_base_hits), default=None)
first_gated = min((g["ts"] for g in gated if g["hit"]), default=None)

res = {
    "device": config.DEVICE, "platform": platform.platform(),
    "frames": n, "calm_frames": len(calm), "fire_frames": len(fire),
    "stage2_runs": ran, "stage2_pct": round(100 * ran / n, 1),
    "baseline_sec": round(t_base, 2), "gated_sec": round(t_gated, 2),
    "saved_pct": round(100 * (1 - t_gated / t_base), 1),
    "calm_false_triggers": calm_triggers,
    "calm_heavy_model_detections": calm_model_hits,
    "fire_frames_with_detection_baseline": len(fire_base_hits),
    "fire_frames_missed_by_gate": len(missed),
    "first_detection_baseline_sec": first_base,
    "first_detection_gated_sec": first_gated,
    "detection_delay_sec": (round(first_gated - first_base, 2)
                            if first_base is not None and first_gated is not None else None),
}

print("\n=== BENCHMARK ===")
for k, v in res.items():
    print(f"{k:<38}: {v}")
with open("data/benchmark_results.json", "w") as f:
    json.dump(res, f, indent=2)
print("\nsaved data/benchmark_results.json")