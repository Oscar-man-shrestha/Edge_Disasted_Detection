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
