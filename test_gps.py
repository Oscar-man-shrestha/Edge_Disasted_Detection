from frame_source import FrameSource
from gps_sim import GPSSim

gps = GPSSim()
print(f"path {gps.total:.0f} m, lasts {gps.total / gps.speed:.0f} s at {gps.speed} m/s")

t0 = None
for n, (idx, ts, frame) in enumerate(FrameSource().frames(), start=1):
    t0 = ts if t0 is None else t0
    lat, lon = gps.position(ts - t0)
    if n % 10 == 1:
        print(f"{n:>4}  t={ts - t0:5.1f}s  lat={lat:.6f}  lon={lon:.6f}")