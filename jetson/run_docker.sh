#!/usr/bin/env bash
# Run a command inside the edge-drone container with this repo mounted at /work.
#   jetson/run_docker.sh                         # interactive shell
#   EDGE_DEVICE=0 jetson/run_docker.sh python3 benchmark.py
# All EDGE_* and GS_* variables in your shell are passed into the container.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
IMAGE="${EDGE_IMAGE:-edge-drone}"
DOCKER="${DOCKER:-sudo docker}"

args=(--rm --runtime nvidia --ipc host --network host -v "$REPO":/work -w /work)
# Run as the owner of the repo (eshaan), not root, so snapshots, alerts.db and engines
# stay deletable without sudo; works the same under sudo or the systemd service.
# EDGE_DOCKER_ROOT=1 runs as root like before.
if [ "${EDGE_DOCKER_ROOT:-0}" != "1" ]; then
  args+=(--user "$(stat -c '%u:%g' "$REPO")" -e HOME=/tmp)
  for g in video dialout i2c; do                       # camera + GPU, serial GPS, power sensor
    gid=$(getent group "$g" | cut -d: -f3) && [ -n "$gid" ] && args+=(--group-add "$gid")
  done
fi
# Ultralytics: never try the internet (field use), keep its settings in the repo.
args+=(-e YOLO_OFFLINE=1 -e YOLO_CONFIG_DIR=/work/.ultralytics)
# Same timezone as the Nano, so alert times match the ground station. Only the
# localtime file: the image has no zoneinfo database, so TZ=<name> would fall back to UTC.
[ -e /etc/localtime ] && args+=(-v /etc/localtime:/etc/localtime:ro)
[ -S /tmp/argus_socket ] && args+=(-v /tmp/argus_socket:/tmp/argus_socket)   # CSI camera daemon
for d in /dev/video* /dev/ttyTHS1 /dev/ttyACM* /dev/ttyUSB*; do
  [ -e "$d" ] && args+=(--device "$d")                                       # USB cam, UART, FC
done
[ -t 0 ] && args+=(-it)
# pass values explicitly: sudo would strip the variables themselves
while IFS='=' read -r name value; do
  args+=(-e "$name=$value")
done < <(env | grep -E '^(EDGE|GS)_[A-Z0-9_]*=' || true)

[ $# -eq 0 ] && set -- bash
exec $DOCKER run "${args[@]}" "$IMAGE" "$@"
