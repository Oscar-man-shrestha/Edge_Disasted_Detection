import sys
import json
import cv2

W, H, FPS = 640, 360, 25
MAX_CALM_SEC = 30


def write_clip(path, writer, max_frames=None):
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise SystemExit(f"Cannot open {path}")
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    acc, written = 0.0, 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frame = cv2.resize(frame, (W, H))
        acc += FPS / src_fps          # resample source fps to FPS
        while acc >= 1.0:
            writer.write(frame)
            written += 1
            acc -= 1.0
            if max_frames and written >= max_frames:
                cap.release()
                return written
    cap.release()
    return written


calm_path, fire_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]

writer = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
calm_frames = write_clip(calm_path, writer, max_frames=MAX_CALM_SEC * FPS)
fire_frames = write_clip(fire_path, writer)
writer.release()

labels = {
    "fps": FPS,
    "fire_start_sec": calm_frames / FPS,
    "total_sec": (calm_frames + fire_frames) / FPS,
}
with open(out_path.rsplit(".", 1)[0] + "_labels.json", "w") as f:
    json.dump(labels, f, indent=2)

print(f"calm: {calm_frames/FPS:.1f}s | fire: {fire_frames/FPS:.1f}s")
print("labels:", labels)