from frame_source import FrameSource
from stage1_gate import Stage1Gate
from stage2_detector import Stage2Detector

gate = Stage1Gate()
det = Stage2Detector()

total = ran = 0
s1_ms, s2_ms = [], []

for idx, ts, frame in FrameSource().frames():
    total += 1
    r = gate.check(frame)
    s1_ms.append(r["ms"])
    dets = []
    if r["trigger"]:
        dets, ms = det.detect(frame)
        ran += 1
        s2_ms.append(ms)
    if total % 5 == 0 or dets:
        summary = [(d["type"], round(d["conf"], 2)) for d in dets]
        print(f"{total:>4} {ts:>6.2f}s trig={str(r['trigger']):<5} {summary}")

avg1 = sum(s1_ms) / len(s1_ms)
s2_use = s2_ms[1:] if len(s2_ms) > 1 else s2_ms      # skip the warm-up inference
avg2 = sum(s2_use) / max(len(s2_use), 1)
baseline = total * avg2                               # heavy model on every frame
gated = total * avg1 + ran * avg2                     # Stage 1 on all, Stage 2 only when triggered

print("\n--- summary ---")
print(f"frames sampled      : {total}")
print(f"Stage 2 ran on      : {ran} ({100*ran/total:.1f}%)")
print(f"avg Stage 1 / frame : {avg1:.2f} ms")
print(f"avg Stage 2 / frame : {avg2:.1f} ms")
print(f"baseline (YOLO on all frames) : {baseline/1000:.2f} s")
print(f"gated pipeline                : {gated/1000:.2f} s")
print(f"estimated compute saved       : {100*(1-gated/baseline):.1f}%")