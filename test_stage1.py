from frame_source import FrameSource
from stage1_gate import Stage1Gate

gate = Stage1Gate()
total = flagged = triggered = 0

print(f"{'n':>4} {'t(s)':>6} {'fire%':>7} {'diff%':>7} {'flag':>5} {'streak':>6} {'TRIG':>5} {'ms':>6}")
for idx, ts, frame in FrameSource().frames():
    r = gate.check(frame)
    total += 1
    flagged += r["flagged"]
    triggered += r["trigger"]
    print(f"{total:>4} {ts:>6.2f} {r['fire_frac']*100:>6.2f}% {r['diff_frac']*100:>6.2f}% "
          f"{str(r['flagged']):>5} {r['streak']:>6} {str(r['trigger']):>5} {r['ms']:>6.2f}")

print("\n--- summary ---")
print(f"frames sampled : {total}")
print(f"flagged        : {flagged}")
print(f"Stage 2 wakes  : {triggered}  ({100*triggered/max(total,1):.1f}% of frames)")