#!/usr/bin/env bash
# One-time host setup for the Jetson Nano (JetPack 4.6). Safe to re-run.
#   jetson/setup_nano.sh
# Steps: check JetPack, max performance mode, Docker + NVIDIA runtime, swap,
# build the edge-drone image, check the camera / OpenCV GStreamer support.
set -uo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
ok()   { echo -e "  \e[32mOK\e[0m   $*"; }
warn() { echo -e "  \e[33mWARN\e[0m $*"; }
step() { echo; echo "== $*"; }

step "Board"
if [ -f /etc/nv_tegra_release ]; then
  ok "$(head -1 /etc/nv_tegra_release)"
  grep -q "R32" /etc/nv_tegra_release || warn "not L4T R32 (JetPack 4). The Docker image below targets JetPack 4."
else
  warn "/etc/nv_tegra_release not found: is this a Jetson?"
fi
model=$(tr -d '\0' < /proc/device-tree/model 2>/dev/null || echo unknown)
ok "model: $model"

step "Power mode (MAXN + max clocks)"
if command -v nvpmodel >/dev/null; then
  sudo nvpmodel -m 0 && ok "nvpmodel -m 0 (MAXN, 10 W)"
  sudo jetson_clocks && ok "jetson_clocks"
  warn "MAXN needs the 5V 4A barrel jack with the J48 jumper; micro-USB power will brown out under load"
else
  warn "nvpmodel not found"
fi

step "Docker + NVIDIA runtime"
if command -v docker >/dev/null; then
  ok "$(docker --version)"
  if sudo docker info 2>/dev/null | grep -qi "nvidia"; then ok "nvidia runtime registered"
  else warn "nvidia runtime not listed in 'docker info' (install nvidia-container-runtime)"; fi
else
  warn "docker missing: sudo apt-get install -y docker.io nvidia-container-runtime"
fi

step "Swap (TensorRT engine builds need memory)"
swap_mb=$(free -m | awk '/Swap/ {print $2}')
if [ "${swap_mb:-0}" -lt 4000 ]; then
  if [ ! -f /swapfile ]; then
    echo "  swap is ${swap_mb} MB; creating a 4 GB /swapfile"
    sudo fallocate -l 4G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile \
      && sudo swapon /swapfile && echo "/swapfile none swap sw 0 0" | sudo tee -a /etc/fstab >/dev/null \
      && ok "4 GB swapfile enabled"
  else
    sudo swapon /swapfile 2>/dev/null; ok "/swapfile present"
  fi
else
  ok "swap ${swap_mb} MB"
fi

step "Build edge-drone image (first time pulls ~several GB)"
sudo docker build -t edge-drone "$REPO/jetson" && ok "image edge-drone built" || warn "docker build failed"

step "Files that are not in git"
for f in weights/yolov8n.pt weights/fire_smoke.pt data/mixed_test.mp4 data/mixed_test_labels.json; do
  [ -f "$REPO/$f" ] && ok "$f" || warn "missing $f (copy it from the laptop, e.g. scp)"
done

step "Camera"
ls /dev/video* >/dev/null 2>&1 && ok "video devices: $(ls /dev/video* | tr '\n' ' ')" || warn "no /dev/video* (CSI camera not detected or not connected)"
host_gst=$(python3 -c "import cv2,re; print('YES' if re.search(r'GStreamer:\s+YES', cv2.getBuildInformation()) else 'NO')" 2>/dev/null || echo "no cv2")
ok "host OpenCV GStreamer: $host_gst (camera_bridge.py runs here)"
cont_gst=$(sudo docker run --rm edge-drone python3 -c "import cv2,re; print('YES' if re.search(r'GStreamer:\s+YES', cv2.getBuildInformation()) else 'NO')" 2>/dev/null | tail -1)
ok "container OpenCV GStreamer: ${cont_gst:-unknown}"
if [ "$cont_gst" != "YES" ]; then
  echo "       -> for a CSI camera use the bridge: python3 jetson/camera_bridge.py"
  echo "          and EDGE_SOURCE=http://127.0.0.1:8090/stream.mjpg"
fi

step "Flight-controller UART (only for EDGE_GPS=mavlink)"
if systemctl is-enabled nvgetty >/dev/null 2>&1; then
  warn "serial console nvgetty owns /dev/ttyTHS1. To use it for MAVLink: sudo systemctl disable --now nvgetty"
else
  ok "/dev/ttyTHS1 free"
fi

echo
echo "Next: EDGE_DEVICE=0 jetson/run_docker.sh python3 check_fire_model.py   (see JETSON.md)"
