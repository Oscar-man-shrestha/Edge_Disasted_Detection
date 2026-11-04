#!/usr/bin/env bash
# Turn the Nano's Wi-Fi card into a field access point for the ground-station laptop.
#   sudo jetson/hotspot.sh                          # SSID DRONE-EDGE, random password (printed once)
#   sudo jetson/hotspot.sh --password 'my-pass-123' --ssid DRONE-EDGE --ifname wlan0
#   sudo jetson/hotspot.sh --off                    # back to normal Wi-Fi client mode
# The Nano becomes 10.42.0.1 and hands out addresses to the laptop (DHCP, "shared" mode).
# The connection autostarts at boot. The ground station's beacon finds the drone side automatically.
set -euo pipefail
SSID="DRONE-EDGE"; PW=""; IFNAME=""; CON="drone-edge"; OFF=0
while [ $# -gt 0 ]; do
  case "$1" in
    --ssid) SSID="$2"; shift 2 ;;
    --password) PW="$2"; shift 2 ;;
    --ifname) IFNAME="$2"; shift 2 ;;
    --off) OFF=1; shift ;;
    -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
    *) echo "unknown option: $1"; exit 1 ;;
  esac
done
[ "$(id -u)" -eq 0 ] || { echo "run with sudo"; exit 1; }
command -v nmcli >/dev/null || { echo "nmcli (NetworkManager) not found"; exit 1; }

if [ "$OFF" -eq 1 ]; then
  nmcli con down "$CON" 2>/dev/null || true
  nmcli con modify "$CON" connection.autoconnect no 2>/dev/null || true
  echo "hotspot '$CON' off (and will not start at boot). Delete it with: sudo nmcli con delete $CON"
  exit 0
fi

if [ -z "$IFNAME" ]; then
  IFNAME=$(nmcli -t -f DEVICE,TYPE dev | awk -F: '$2=="wifi"{print $1; exit}')
  [ -n "$IFNAME" ] || { echo "no Wi-Fi device found (is the M.2 Wi-Fi card fitted?)"; exit 1; }
fi
if command -v iw >/dev/null; then
  if ! iw list 2>/dev/null | sed -n '/Supported interface modes/,/^\s*$/p' | grep -q '\* AP$'; then
    echo "this Wi-Fi card does not report AP (access point) mode; use a phone hotspot or router instead"
    exit 1
  fi
fi
if [ -z "$PW" ]; then
  PW=$(openssl rand -base64 9 | tr -d '/+=' | cut -c1-12)
  GENERATED=1
fi
[ ${#PW} -ge 8 ] || { echo "password must be at least 8 characters"; exit 1; }

nmcli con delete "$CON" >/dev/null 2>&1 || true
nmcli con add type wifi ifname "$IFNAME" con-name "$CON" autoconnect yes ssid "$SSID" \
  802-11-wireless.mode ap 802-11-wireless.band bg ipv4.method shared \
  wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$PW" >/dev/null
nmcli con up "$CON" >/dev/null
echo "hotspot up: SSID '$SSID' on $IFNAME, Nano at 10.42.0.1, starts at boot"
if [ "${GENERATED:-0}" -eq 1 ]; then
  echo "password (shown once, write it down): $PW"
fi
echo "on the laptop: join '$SSID', then run: python ground_station/app.py"
