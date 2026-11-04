#!/usr/bin/env bash
# Start the pipeline automatically at boot (no monitor/keyboard on the drone).
#   sudo jetson/install_service.sh                 # pipeline only
#   sudo jetson/install_service.sh --camera-bridge # also the CSI camera bridge
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "run with sudo"; exit 1; }
REPO="$(cd "$(dirname "$0")/.." && pwd)"

sed "s|REPO_DIR|$REPO|g" "$REPO/jetson/edge-drone.service" > /etc/systemd/system/edge-drone.service
units=(edge-drone.service)
if [ "${1:-}" = "--camera-bridge" ]; then
  sed "s|REPO_DIR|$REPO|g" "$REPO/jetson/edge-camera-bridge.service" \
    > /etc/systemd/system/edge-camera-bridge.service
  units+=(edge-camera-bridge.service)
fi
if [ ! -f /etc/default/edge-drone ]; then
  cp "$REPO/jetson/edge-drone.env" /etc/default/edge-drone
  echo "created /etc/default/edge-drone: set EDGE_SERVER_URL to your laptop's IP"
fi
systemctl daemon-reload
systemctl enable "${units[@]}"
echo "enabled: ${units[*]}"
echo "start now:  sudo systemctl start edge-drone"
echo "logs:       journalctl -u edge-drone -f"
echo "disable:    sudo systemctl disable --now ${units[*]}"
