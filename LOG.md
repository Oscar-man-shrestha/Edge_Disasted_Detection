# Bring-up Log: Jetson Nano + Ground Station

A running record of what we did on the real hardware, what worked, what broke and how we fixed it.
Newest entries at the bottom of each day. Branch: `temp-jetson-fixes` (never `main`).

**Hardware:** Jetson Nano Dev Kit B01 (JetPack 4.6.1 / L4T R32.7.1, user `eshaan`, host `eshaan-desktop`) ·
Lenovo FHD USB webcam · u-blox NEO-M8N GPS + compass · 5 V barrel power · MacBook Air M1 as ground station.

**Status at a glance**

| Item | State |
|---|---|
| Nano boots headless, reachable from the Mac over USB | ✅ |
| Nano internet (Wi-Fi) | ⚠️ works on `lowey`, but the hotspot drops often |
| Project code on the Nano (`~/Edge_Disasted_Detection_Project`, branch `temp-jetson-fixes`) | ✅ |
| Models: `weights/yolov8n.pt` (6.3 MB), `weights/fire_smoke.pt` (5.2 MB) | ✅ |
| Webcam detected (`/dev/video0`, USB ID `17ef:4831 Lenovo`) | ✅ |
| Docker base image `ultralytics/ultralytics:latest-jetson-jetpack4` | ✅ 5.6 GB, finished 16:31 (Nano clock) |
| Our image `edge-drone` | ✅ built |
| AI check on the GPU (both models, real webcam frame) | ✅ |
| TensorRT FP16 engines | ⏳ building overnight |
| Ground station on the Mac (port 5050) | ✅ running, "Waiting for drone" |
| Nano → Mac station link over USB (`192.168.55.100:5050`) | ✅ tested |
| Camera snapshot / AI check / first live run | ⏳ next |
| GPS wiring | ⏳ later |

---

## 2026-11-05

### 1. Headless connection from the Mac (USB)
- Nano powered from the **5 V barrel jack** (J48 jumper on), Mac connected with **micro-USB → USB-C** to the Nano's micro-USB port.
- Mac sees the Nano as a USB network device: a volume `L4T-README` appears, interface `en7` gets **192.168.55.100**, the Nano is **192.168.55.1**.
- Serial console also appears as `/dev/cu.usbmodem…` (backup if the network ever fails).
- Login: `ssh eshaan@192.168.55.1`. (Mistake fixed: the username is `eshaan`, not the display name.)
- Desktop GUI disabled to save RAM: `sudo systemctl set-default multi-user.target`.
- Board check: R32.7.1, 34 GB free on the SD card, 3.9 GB RAM, 5.9 GB swap, Docker 20.10.7 with the NVIDIA runtime.

**Lesson:** the prompt tells you where a command runs. `oscar@Oscars-MacBook-Air` = Mac, `eshaan@eshaan-desktop` = Nano.
Commands typed with `!` in the Claude chat always run on the **Mac**.

### 2. Power warning
- Saw "system throttled due to over-current". This is the board protecting itself, not damage.
- Use a 5 V **4 A** barrel brick with the J48 jumper. If it keeps happening: `sudo nvpmodel -m 1` (5 W mode).
- Always shut down with `sudo shutdown -h now` before unplugging.

### 3. Wi-Fi (the long part)
| Problem | Cause | Fix |
|---|---|---|
| `Wi-Fi network could not be found` on lowey | lowey was on **5 GHz ch 44**; Nano Wi-Fi country is `00` (world), which can't join most 5 GHz channels | lowey switched to **2.4 GHz ch 1/6**, then it joined. (`sudo iw reg set IN` did not stick.) |
| `Secrets were required` | wrong password typed (the Nano login password instead of the Wi-Fi one) | use the Wi-Fi password |
| Several stale profiles `lowey 1…5` fighting | each `nmcli dev wifi connect` made a new profile | set them to `autoconnect no`; use only `lowey` |
| `lookup auth.docker.io … i/o timeout` | DNS through lowey timing out | `sudo systemctl restart systemd-resolved` + `sudo ln -sf /run/systemd/resolve/resolv.conf /etc/resolv.conf` (uses lowey's DNS directly). **Forcing 8.8.8.8 made it worse; undone.** |
| Connected but no internet, `reason 5` disconnects | lowey is a phone hotspot that sleeps / was **full of devices** | keep phone awake, charging, hotspot timeout = Never, free a device slot |
| `IP configuration could not be reserved` | hotspot not handing out addresses (full / no data) | restart hotspot on the phone |
| AMRITA-BLR-Connect | campus **WPA2-Enterprise** + **FortiGate login page** (`10.200.0.1:1000`) | the saved `AMRITA-BLR-Connect` profile joins, but internet stays blocked until the portal login. Helper `~/campus_login.py` on the Nano does the portal login (you type the password). Not used in the end: we went back to lowey. |

Made permanent so we don't fight this again:
- `eshaan` may control Wi-Fi **without sudo** (polkit rule `/etc/polkit-1/localauthority/50-local.d/eshaan-nm.pkla`).
- `lowey` auto-connects with highest priority and retries forever (`connection.autoconnect-retries 0`).

### 4. Getting the code onto the Nano
- `git clone` failed: the repo is **private** (GitHub needs a token, not a password) and old Ubuntu 18.04 TLS (`gnutls_handshake() failed`).
- Instead, streamed the project from the Mac over USB (run on the **Mac**, in the repo folder):
  ```bash
  COPYFILE_DISABLE=1 tar --no-xattrs --exclude=node_modules --exclude=.claude --exclude=data/demo -czf - . | ssh eshaan@192.168.55.1 'mkdir -p ~/Edge_Disasted_Detection_Project && tar -xzf - -C ~/Edge_Disasted_Detection_Project'
  ```
- First attempt was accidentally run on the Nano (copied its own home folder); deleted and redone from the Mac.
- Result: `~/Edge_Disasted_Detection_Project` on the Nano, branch `temp-jetson-fixes` ✅.

### 5. Models (downloaded on the Nano)
```bash
wget -4 -c --tries=20 --read-timeout=20 -O weights/yolov8n.pt https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8n.pt
wget -4 -c --tries=20 --read-timeout=20 -O weights/fire_smoke.pt https://huggingface.co/seawsurf/fire_yolo/resolve/main/weights/best.pt
```
- The fire model lives in the **`weights/` folder** of the Hugging Face repo; the old link (without `/weights/`) gave 404. GUIDE.md fixed (commit `f828880`).
- `-4` (IPv4) and `-c` (resume) were needed because lowey's IPv6 path and connection were flaky.

### 6. Webcam
- Plugged into a blue USB 3.0 port. `ls /dev/video*` → `/dev/video0`; `lsusb` → `17ef:4831 Lenovo` ✅.
- **Snapshot test (no Docker needed)**, on the Nano, using GStreamer and the camera's MJPG mode:
  ```bash
  gst-launch-1.0 -q v4l2src device=/dev/video0 num-buffers=30 ! image/jpeg,width=1280,height=720 ! multifilesink location=/tmp/cam_%02d.jpg
  scp eshaan@192.168.55.1:/tmp/cam_29.jpg .      # on the Mac, to look at it
  ```
  Result: clear **1280x720** colour image of the room (frame 30, so auto-exposure has settled) ✅.

### 7. One-time setup `jetson/setup_nano.sh`
- OK: board, MAXN power mode, Docker + NVIDIA runtime, swap 6 GB, both models present.
- Expected WARNs: test video missing (optional), camera (was not plugged in yet), `nvgetty` on `/dev/ttyTHS1` (only matters for a flight controller).
- **Docker build failed** each time the Wi-Fi/DNS dropped. Now downloading the base image separately with retries:
  ```bash
  until docker pull ultralytics/ultralytics:latest-jetson-jetpack4; do sleep 10; done
  ```
  Progress: all layers done except one (~646 MB). When it finishes: `docker build -t edge-drone jetson` (or re-run `jetson/setup_nano.sh`).
- After a hotspot drop the pull **froze at 0 KB/s** even with internet back (stuck on a dead connection).
  Fix: kill the pull client and start it again (no sudo needed): it resumed at ~350 KB/s.
- Made it self-healing: `~/pull-retry.sh` on the Nano (started with `setsid nohup`, survives SSH disconnects)
  restarts `docker pull` whenever it dies, until the image exists. Logs: `~/pull.log`, `~/pull-retry.log`.
- A watcher then runs `docker build -t edge-drone jetson` automatically.

### 8. Remote control from the Mac (so Claude can run Nano commands)
- Mac SSH key copied to the Nano (`ssh-copy-id`), so `ssh eshaan@192.168.55.1` needs no password.
- `eshaan` added to the `docker` group, so Docker works without sudo.

### 9. Mac side
- Mac disk was **full** (117 MB free): broke SSH `known_hosts`, the demo drone, and Claude's tools.
  Freed with `conda clean --all -y` (~1 GB) etc. Now ~6 GB free. Caches (7 GB) can still be cleared later.
- Ground station restarted with a **clean data folder** and a beacon on the USB link:
  ```bash
  GS_DATA_DIR=ground_station/received/live GS_BEACON_TARGETS=255.255.255.255,10.42.0.255,192.168.55.255 python ground_station/app.py
  ```
  Dashboard: http://localhost:5050 → "Waiting for drone". The Nano can reach it at `http://192.168.55.100:5050` ✅.

### 10. Docker image built
- Base image download finished (`PULL-FINISHED 16:31:39`), then `docker build -t edge-drone jetson` ✅ (5.62 GB).
- `pymavlink` failed to install inside the image. Fine: only needed for `EDGE_GPS=mavlink` (flight controller); our GPS is NMEA.
- Run things without sudo: `DOCKER=docker jetson/run_docker.sh python3 <script>.py` (eshaan is in the docker group).

Inside the container:

| | |
|---|---|
| Python | 3.8.0 |
| PyTorch | 1.11.0a0, **CUDA True**, GPU `NVIDIA Tegra X1` |
| Ultralytics | 8.4.203 (loads the YOLO26 fire model without upgrading) |
| OpenCV | 5.0.0, GStreamer **NO** (fine for the USB webcam via V4L2; a CSI camera would need `jetson/camera_bridge.py`) |

### 11. AI check (PyTorch, GPU, FP32, 640 px, on the 1280x720 webcam photo)

| Model | Classes | Time / frame | Result |
|---|---|---|---|
| `yolov8n.pt` (person) | 80 COCO | **365 ms** | bed 0.87, table 0.44, cup 0.44, chairs, **person 0.29** (seen from behind) |
| `fire_smoke.pt` (YOLO26) | fire, smoke | **269 ms** | nothing, correct (no fire in the room) |

Pictures with boxes saved on the Nano: `data/ai_check_person.jpg`, `data/ai_check_fire.jpg`.
`benchmark.py` needs `data/mixed_test.mp4` + labels, which aren't on the Nano yet, so timing is measured on the webcam frame instead.

### 12. TensorRT export (started 21:35 Nano clock)
```bash
DOCKER=docker setsid nohup jetson/run_docker.sh python3 export_trt.py > ~/trt_export.log 2>&1 &
```
Builds FP16 engines `weights/yolov8n.engine` and `weights/fire_smoke.engine` (device-specific, never commit them).

### Mistake to undo on the Mac
- A Nano-only command was run on the Mac with `sudo`, creating `/etc/sudoers.d/edge-docker` **on the Mac**.
  Harmless (it names a user that doesn't exist on the Mac). **Removed** with `sudo rm /etc/sudoers.d/edge-docker` ✅.

### Security to-do
- The Nano login password and the lowey Wi-Fi password were shared in chat. Change the Nano password with `passwd` when convenient.

### Next
1. Finish the Docker download → build `edge-drone`.
2. Camera snapshot test (`True (720, 1280, 3)`).
3. AI check: `jetson/run_docker.sh python3 check_fire_model.py`.
4. First live run: Nano camera → YOLO → alerts on the Mac dashboard.
5. GPS: NEO-M8N via a USB-TTL adapter (CP2102/CH340/FTDI) or the 40-pin header UART.
