#!/usr/bin/env bash
# Start the ground station on the laptop:  ./start_station.sh
# Dashboard: http://localhost:5050   (Ctrl+C to stop)
# The Nano finds it by itself (UDP beacon) over the USB cable or its hotspot.
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -x venv/bin/python ]; then
  echo "first run: creating venv/ (small, no PyTorch needed for the station)"
  python3 -m venv venv
  venv/bin/pip install -q flask requests numpy opencv-python-headless pyserial pytest
fi
export GS_DATA_DIR="${GS_DATA_DIR:-ground_station/received/live}"
exec venv/bin/python ground_station/app.py
