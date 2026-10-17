from frame_source import FrameSource

count = 0
for idx, ts, frame in FrameSource().frames():
    count += 1
    print(f"sampled frame #{count} | source idx {idx} | t={ts:.2f}s | shape={frame.shape}")
    if count >= 10:
        break
print("OK")