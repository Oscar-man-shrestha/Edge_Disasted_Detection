# Central settings. Change values here, never inside other files.
# A few values can be overridden by environment variables (see README).
import os

# --- Input ---
# Use a video path for guaranteed demos, an int (0) for a USB camera,
# or "csi" for the Jetson Nano CSI camera (GStreamer, see CSI_* below).
SOURCE = os.environ.get("EDGE_SOURCE", "data/mixed_test.mp4")
if SOURCE.isdigit():
    SOURCE = int(SOURCE)

# --- Jetson CSI camera (used when SOURCE == "csi") ---
CSI_SENSOR_ID = 0              # 0 or 1, the two CSI connectors on the Nano B01
CSI_CAPTURE_WIDTH = 1280
CSI_CAPTURE_HEIGHT = 720
CSI_CAPTURE_FPS = 30
CSI_FLIP = 0                   # nvvidconv flip-method, 2 = rotate 180
SAMPLE_INTERVAL_SEC = 0.5      # pull one frame every 0.5 s
FRAME_WIDTH = 640              # resize for speed on Jetson
FRAME_HEIGHT = 360

# --- Stage 1 (filled in at step 2) ---
CONSECUTIVE_FLAGS_NEEDED = 3   # flagged frames in a row before waking Stage 2

# --- Stage 2 (filled in at step 3) ---
PERSON_WEIGHTS = os.environ.get("EDGE_PERSON_WEIGHTS", "weights/yolov8n.pt")
FIRE_WEIGHTS = os.environ.get("EDGE_FIRE_WEIGHTS", "weights/fire_smoke.pt")
CONF_THRESHOLD = 0.3

# --- Alerts (filled in at step 5) ---
DB_PATH = "data/alerts.db"
SERVER_URL = os.environ.get("EDGE_SERVER_URL", "http://localhost:5000/alert")

# --- Stage 1 gate thresholds (tune these on your videos) ---
FIRE_HSV_LOWER = (0, 120, 180)    # H, S, V lower bound for fire-orange
FIRE_HSV_UPPER = (35, 255, 255)   # H, S, V upper bound
FIRE_PIXEL_FRACTION = 0.01        # flag if >1% of frame is fire-colored
DIFF_PIXEL_THRESHOLD = 30         # per-pixel brightness change that counts as "changed"
DIFF_FRACTION = 0.15              # flag if >15% of pixels changed

# --- Device ("cpu" on laptop, "0" = first CUDA GPU on the Jetson) ---
DEVICE = os.environ.get("EDGE_DEVICE", "cpu")

# --- GPS simulation ---
FLIGHT_PATH_CSV = "data/flight_path.csv"
DRONE_SPEED_MPS = 5.0          # simulated ground speed, metres per second

# --- Alerts ---
ALERT_COOLDOWN_SEC = 10        # same alert type stays quiet this long after firing
PERSON_ALERT_CONF = 0.5        # people need higher confidence than fire/smoke
SNAPSHOT_DIR = "data/snapshots"
