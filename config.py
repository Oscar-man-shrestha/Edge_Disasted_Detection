# Central settings. Change values here, never inside other files.
# A few values can be overridden by environment variables (see README).
import os
import socket


def _env_bool(name, default):
    v = os.environ.get(name)
    return default if v is None else v.strip().lower() in ("1", "true", "yes", "on")


# --- Input ---
# A video path for guaranteed demos, an int (0) for a USB camera, "csi" for the
# Jetson CSI camera (GStreamer), or a URL such as the camera bridge
# "http://127.0.0.1:8090/stream.mjpg" (see jetson/camera_bridge.py).
SOURCE = os.environ.get("EDGE_SOURCE", "data/mixed_test.mp4")
if SOURCE.isdigit():
    SOURCE = int(SOURCE)
SAMPLE_INTERVAL_SEC = 0.5      # pull one frame every 0.5 s
FRAME_WIDTH = 640              # resize for speed on Jetson
FRAME_HEIGHT = 360

# --- USB webcam (used when SOURCE is an int, e.g. the Lenovo FHD webcam = 0) ---
# MJPG lets USB 2.0 webcams deliver 720p at full frame rate; raw YUYV is much slower.
USB_CAPTURE_WIDTH = 1280
USB_CAPTURE_HEIGHT = 720
USB_FOURCC = "MJPG"

# --- Jetson CSI camera (used when SOURCE == "csi") ---
CSI_SENSOR_ID = 0              # 0 or 1, the two CSI connectors on the Nano B01
CSI_CAPTURE_WIDTH = 1280
CSI_CAPTURE_HEIGHT = 720
CSI_CAPTURE_FPS = 30
CSI_FLIP = 0                   # nvvidconv flip-method, 2 = rotate 180

# --- Stage 1 gate (tune these on your videos) ---
CONSECUTIVE_FLAGS_NEEDED = 3      # flagged frames in a row before waking Stage 2
FIRE_HSV_LOWER = (0, 120, 180)    # H, S, V lower bound for fire-orange
FIRE_HSV_UPPER = (35, 255, 255)   # H, S, V upper bound
FIRE_PIXEL_FRACTION = 0.01        # flag if >1% of frame is fire-colored
DIFF_PIXEL_THRESHOLD = 30         # per-pixel brightness change that counts as "changed"
DIFF_FRACTION = 0.15              # flag if >15% of pixels changed
# Camera-motion compensation: align the previous frame to the current one before
# differencing, so drone movement itself does not count as "change".
MOTION_COMPENSATION = _env_bool("EDGE_MOTION_COMP", True)
MOTION_MIN_FEATURES = 20          # fewer tracked corners than this -> skip alignment

# --- Stage 2 ---
PERSON_WEIGHTS = os.environ.get("EDGE_PERSON_WEIGHTS", "weights/yolov8n.pt")
FIRE_WEIGHTS = os.environ.get("EDGE_FIRE_WEIGHTS", "weights/fire_smoke.pt")
CONF_THRESHOLD = 0.3
IMG_SIZE = 640                 # must match the imgsz used for TensorRT/ONNX export
# After Stage 2 has confirmed something, run it only on every Nth triggered frame
# while detections keep coming. 1 = run on every triggered frame (old behaviour).
STAGE2_EVERY_N_WHILE_CONFIRMED = int(os.environ.get("EDGE_STAGE2_EVERY_N", "3"))

# --- Device ("cpu" on laptop, "0" = first CUDA GPU on the Jetson) ---
DEVICE = os.environ.get("EDGE_DEVICE", "cpu")

# --- GPS ---
# "sim"     follows FLIGHT_PATH_CSV (no hardware).
# "nmea"    a GPS module such as the u-blox NEO-M8N on a serial port: the Nano UART
#           /dev/ttyTHS1 (40-pin header pins 8/10) or a USB-serial adapter /dev/ttyUSB0.
# "mavlink" GLOBAL_POSITION_INT from a flight controller (needs pymavlink).
GPS_MODE = os.environ.get("EDGE_GPS", "sim")
GPS_PORT = os.environ.get("EDGE_GPS_PORT", "/dev/ttyTHS1")
GPS_BAUD = int(os.environ.get("EDGE_GPS_BAUD", "0"))   # 0 = auto-detect (M8N default 9600)
GPS_MAX_FIX_AGE_SEC = 5        # older fixes count as "no fix" in alerts
MAVLINK_URL = os.environ.get("EDGE_MAVLINK_URL", "/dev/ttyTHS1,57600")  # or "udpin:0.0.0.0:14550"
FLIGHT_PATH_CSV = "data/flight_path.csv"
DRONE_SPEED_MPS = 5.0          # simulated ground speed, metres per second

# --- Alerts ---
DB_PATH = os.environ.get("EDGE_DB_PATH", "data/alerts.db")
# "auto" = find the ground station by its UDP beacon; or a fixed "http://host:port"
SERVER_URL = os.environ.get("EDGE_SERVER_URL", "auto")
ALERT_COOLDOWN_SEC = 10        # same alert type stays quiet this long after firing
PERSON_ALERT_CONF = 0.5        # people need higher confidence than fire/smoke
SNAPSHOT_DIR = "data/snapshots"
FORWARD_INTERVAL_SEC = 5       # (removed in Task 8; replaced by ALERT_FORWARD_INTERVAL_SEC)
FORWARD_CONNECT_TIMEOUT = 1.0  # short, so a dead link does not stall the link thread

# --- Live link to the ground station (link.py) ---
DRONE_ID = os.environ.get("EDGE_DRONE_ID", socket.gethostname())
LINK_KEY = os.environ.get("EDGE_LINK_KEY", "")      # must match GS_LINK_KEY if the station sets one
DISCOVERY_PORT = 5005                               # UDP beacon port of the ground station
TELEMETRY_INTERVAL_SEC = 1.0
PREVIEW_INTERVAL_SEC = 1.5
PREVIEW_WIDTH = 480
PREVIEW_QUALITY = 60
ALERT_FORWARD_INTERVAL_SEC = 2.0

# --- Power measurement (Jetson only; ignored elsewhere) ---
POWER_SAMPLE_SEC = 0.1         # how often the power monitor reads the INA3221 sensor
