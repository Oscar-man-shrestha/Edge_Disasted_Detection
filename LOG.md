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
| TensorRT FP16 engines | ✅ ~2.3x faster, work offline |
| **First live run: Nano webcam → AI → Mac dashboard** | ✅ auto-discovery over USB, LIVE · nano-01 |
| Real person + fire detection, alerts with snapshots | ✅ person 51–95 %, fire 64–80 % |
| Ground station on the Mac (port 5050) | ✅ running, "Waiting for drone" |
| Nano → Mac station link over USB (`192.168.55.100:5050`) | ✅ tested |

| GPS wiring | ⏸ deferred until there is a drone to fly (simulated position meanwhile) |

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
- Took **~11 minutes** for both (ONNX → TensorRT 8.2.0.6), not an hour.
- **Problem:** loading an `.engine` failed with `module 'numpy' has no attribute 'bool'` (TensorRT 8.2 vs numpy 1.24),
  and Ultralytics "fixed" it by **pip-installing numpy 1.23.5 at runtime**, every run, which needs internet. Would break in the field.
- **Fix (commit `7c00e04`):** `jetson/Dockerfile` pins `numpy==1.23.5`; `stage2_detector.py` adds an `np.bool` shim.
  Rebuilt the image, then verified the real detector with **`--network none`** (no internet at all) ✅.

**Speed on the Nano (MAXN, 640 px, median of 10, webcam frame):**

| Model | PyTorch FP32 | TensorRT FP16 | Speed-up |
|---|---|---|---|
| Person (YOLOv8n) | 368 ms | **150 ms** | 2.5x |
| Fire/smoke (YOLO26n) | 267 ms | **129 ms** | 2.1x |
| Both together (real `Stage2Detector`) | ~635 ms | **272 ms** | 2.3x |

### 13. First live run (Nano → Mac, over the USB cable)
On the Nano (TensorRT engines, webcam, simulated GPS until the M8N is wired):
```bash
cd ~/Edge_Disasted_Detection_Project
EDGE_SOURCE=0 EDGE_DEVICE=0 EDGE_PERSON_WEIGHTS=weights/yolov8n.engine EDGE_FIRE_WEIGHTS=weights/fire_smoke.engine \
EDGE_GPS=sim EDGE_DRONE_ID=nano-01 EDGE_SERVER_URL=auto DOCKER=docker \
setsid nohup jetson/run_docker.sh python3 run_pipeline.py > ~/live_run.log 2>&1 &
```
Log:
```
[camera] usb 1280x720 @ 30 fps
[link] ground station found at http://192.168.55.100:5050      ← found by itself via the UDP beacon
```
Telemetry received by the station: 1.8 frames/s sampled (2 per second by design), **Stage 1 gate 22 ms**,
state "scanning", CPU/GPU 30 °C, **2.5 W**, RAM 0.7 / 3.9 GB. Dashboard shows **LIVE · nano-01**, camera preview,
flight panel and the (simulated) track on the map ✅.
Stage 2 did not run because nothing moved in the dark room: the gate is doing its job (no wasted YOLO runs).

To stop it: `docker ps` then `docker stop <id>` (on the Nano).

### 14. Overnight stability test (4 hours, sampled every 10 min from the station)

| | Result |
|---|---|
| Uptime | 4 h without a crash, **24,800+ frames** |
| Frame rate | steady 1.78 fps (the 0.5 s sampling interval, as designed) |
| Stage 1 gate | 20–23 ms per frame |
| CPU / GPU temperature | **29–30.5 °C** the whole time (cool) |
| Power | **2.4–2.8 W** while scanning |
| Link to the Mac | every sample fresh, no drops |
| RAM | 0.67 GB, then **3.25 GB** after the first trigger, then flat (no leak) |
| Triggers / Stage 2 runs / alerts | 2 / 2 / **0**: no false alarms all night |

**Found:** the TensorRT engines only load into GPU memory at the **first** Stage 2 run, which takes **17 s** on the Nano,
so the first real fire or person would have been reported ~17 s late.
**Fix:** `run_pipeline.py` now runs one warm-up detection at startup (`[stage2] models ready (warm-up 17.2 s)`).
Verified on the Nano; 112 tests still pass. The live pipeline was restarted with the fix and keeps running.

Note: 3.25 of 3.9 GB RAM are used once both TensorRT engines are loaded. It's stable, but don't run other heavy jobs
(e.g. a second TensorRT export) at the same time as the live pipeline.

### Mistake to undo on the Mac
- A Nano-only command was run on the Mac with `sudo`, creating `/etc/sudoers.d/edge-docker` **on the Mac**.
  Harmless (it names a user that doesn't exist on the Mac). **Removed** with `sudo rm /etc/sudoers.d/edge-docker` ✅.

### Security to-do
- The Nano login password and the lowey Wi-Fi password were shared in chat. Change the Nano password with `passwd` when convenient.

## 2026-11-06

### 15. Real detection tests ✅
- **Person test:** walked in front of the webcam → **person alerts at 51–95 %**, red "Person detected" banner on the dashboard.
- **Fire test:** fire video on a phone, held in front of the webcam → **fire alerts at 64–80 %**,
  red box drawn exactly around the flames on the phone screen, markers on the map.
- 11 alerts made on the Nano, all 11 delivered to the Mac (`sent=1` in the drone's `data/alerts.db`).
- Stage 2 (YOLO, TensorRT, both models) shown on the dashboard at ~385 ms per triggered frame, including pre/post-processing.

**Bug found: alert thumbnails were broken images on the dashboard.**
- The drone sent every snapshot and the station saved them, but `/snap/<name>` returned **404**.
- Cause: the station was started with a **relative** `GS_DATA_DIR` (`ground_station/received/live`). Files were saved relative
  to the working folder, but Flask served them relative to the app folder (`ground_station/ground_station/...`).
  The cached map tiles had the same problem.
- Fix: `create_app` now makes the data folder absolute. New test `test_snapshot_served_with_relative_data_dir`
  failed before the fix, passes after; full suite **113 passed**. Station restarted; all 5 thumbnails load ✅.

### 16. Review: bugs and weak spots, and what was fixed
Software only, inside the project folder. No firmware, power or system settings touched.

| # | Problem | Fix | Verified |
|---|---|---|---|
| 1 | Snapshot names `fire_3193.1s.jpg` used seconds-since-start, which restart at 0 each run: a new alert could **overwrite an older (maybe unsent) alert's photo** | name now starts with the alert's database id: `12_fire_3193.1s.jpg` (always unique) | new test failed before, passes after |
| 2 | Alert times had no timezone (container clock was UTC, the Mac shows IST) | `wall_time` now ends in the UTC offset, e.g. `2026-11-06 08:19:22 +0530` | new test |
| 3 | Container clock ≠ Nano clock | `run_docker.sh` mounts the Nano's `/etc/localtime` (a `TZ=` name fell back to UTC: the image has no zoneinfo, so it was removed) | container `22:21 -0500` = host |
| 4 | Docker wrote files as **root** (snapshots, `alerts.db`, engines): couldn't delete them without sudo | container runs as the **owner of the repo** (`eshaan`), with the `video` (camera, GPU), `dialout` (GPS serial) and `i2c` (power sensor) groups; same under sudo or the boot service. `EDGE_DOCKER_ROOT=1` = old behaviour. 40 old root-owned files handed back to eshaan | `ps` shows `eshaan python3 run_pipeline.py`, camera + CUDA OK |
| 5 | Ultralytics made a new settings file every run and may try the internet | `YOLO_OFFLINE=1`, settings kept in `.ultralytics/` (git-ignored) | live run starts and works |
| 6 | Camera preview choppy (1 image / 1.5 s) | `EDGE_PREVIEW_SEC` setting; default stays 1.5 s for weak radio links, 0.2 s floor | with `EDGE_PREVIEW_SEC=0.5`: a new preview every **~0.6 s** (was 1.5 s) |

Tests: **116 passed**. Live pipeline restarted on the Nano with all fixes and `EDGE_PREVIEW_SEC=0.5`.

### 17. Commands that need YOUR password (type them on the Nano, prompt `eshaan@eshaan-desktop`)
These change Nano system settings, so only you should run them. All are safe and reversible.
```bash
# India time on the Nano (alerts will show +0530)
sudo timedatectl set-timezone Asia/Kolkata

# Wi-Fi country = India, so 5 GHz networks work (active after reboot)
sudo sed -i 's/^REGDOMAIN=.*/REGDOMAIN=IN/' /etc/default/crda

# Free the GPS serial port (pins 8/10) from the console service
sudo systemctl disable --now nvgetty

# Autostart the drone software at power-on (also sets full-speed clocks at every boot)
sudo jetson/install_service.sh

sudo reboot
```
Undo autostart any time: `sudo systemctl disable --now edge-drone`.
The autostart settings live in `/etc/default/edge-drone` (TensorRT engines, webcam, station found automatically,
`EDGE_GPS=nmea`: alerts say "no GPS fix" until the M8N is wired, the pipeline keeps running).

### 18. GPS deferred
- Decided to leave the GPS until there is a drone to fly: on a desk the position would not change anyway.
- Everything uses the **simulated** position meanwhile (`EDGE_GPS=sim`, also the default in `jetson/edge-drone.env`).
- What we know for later (M8N "Pixhawk-style" cable): big plug = **red 5 V, yellow, green, black GND**;
  small plug (orange, white) = compass, not used. The spare cable's plug is a different size and does not fit.
- Wiring plan (Nano **off**): cut the big plug, join to female jumpers, then
  **red → pin 2, black → pin 6, green → pin 8, yellow → pin 10**. If no data: swap green/yellow (harmless).
  Before that: `sudo systemctl disable --now nvgetty`. Then set `EDGE_GPS=nmea` in `/etc/default/edge-drone`.

### Next
1. **GPS:** later, see section 18.
2. **Field test** over the Nano's own hotspot (DRONE-EDGE) instead of the USB cable.
3. Change the Nano password (`passwd`).

### 19. Autostart at power-on ✅
Run by the user on the Nano (password):
```bash
sudo timedatectl set-timezone Asia/Kolkata
cd ~/Edge_Disasted_Detection_Project && sudo jetson/install_service.sh
sudo reboot
```
After the reboot, with nobody touching the Nano:
- `edge-drone` service **active + enabled**, timezone **Asia/Kolkata (IST, +0530)**
- `[stage2] models ready (warm-up 26.5 s)` → `[camera] usb 1280x720 @ 30 fps` →
  `[link] ground station found at http://192.168.55.100:5050` (about 3 min from power-on to LIVE)
- Dashboard back to LIVE. The drone now reports as **`eshaan-desktop`** (the default ID is the hostname;
  set `EDGE_DRONE_ID=nano-01` in `/etc/default/edge-drone` if you want the old name).
- The "set EDGE_SERVER_URL to your laptop's IP" message from the installer can be ignored: it is `auto`.
- Undo: `sudo systemctl disable --now edge-drone` · logs: `journalctl -u edge-drone -f`

**Mac side:** the ground station had stopped (it ran inside an old Claude session).
New `./start_station.sh` in the repo starts it from its own small `venv/` (flask, requests, numpy,
opencv-headless, pyserial, pytest: 162 MB, **no PyTorch needed** on the laptop). 116 tests pass in it.
To start the station any time:
```bash
cd ~/Edge_Disasted_Detection_Project && ./start_station.sh
```

### 20. Fresh start
All alerts, photos and test pictures deleted on both the Mac and the Nano (user's request, no backup).
Kept only the map tile cache and `data/flight_path.csv` (simulated GPS route).

### 21. Improvements (software only, no system/firmware/power changes)

**One alert per event.** Before: a person standing in view made a new alert every ~10–15 s.
Now (`alert_store.py`): while the same type keeps being seen with gaps < `EVENT_GAP_SEC` (30 s) there is no new
alert, except one every `ALERT_REPEAT_SEC` (60 s) with a fresh photo + position for long events.
Below-threshold person sightings do not keep an event alive.

**Video clips with every alert** (`clip_recorder.py`): JPEG frames from 4 s before to 4 s after the alert
(480 px). They play in any browser; no video codec needed on the Jetson.
- Nano cost measured: **~10 ms per frame** to encode, < 1 MB RAM; at most **200 clips** kept on the SD card.
- Sent to the station only **after** their alert, one per round (`POST /api/clip`), so they never delay a new alert.
  Unknown alert (404) → given up, never retried forever.
- Dashboard: alert detail has a **Photo / Clip** switch with play/pause + slider; 🎞 icon in the list.
- Live result: alerts #3–#7 (person, smoke, fire) all arrived with clips of 15–30 frames.

**Secure link.** Drone and station share a random key in `<repo>/.link_key` (git-ignored, mode 600, same file
on the Mac and the Nano; `EDGE_LINK_KEY` / `GS_LINK_KEY` still override). Station prints
`Link key: ON`. Verified: the old drone process without the key was refused (HTTP 401) until it restarted with it.

**Less lag** (measured on the Nano, nearly idle before and after):

| | Before | After |
|---|---|---|
| Frames checked per second | 1.88 | **3.75** (`EDGE_SAMPLE_SEC=0.25`, floor 0.2) |
| Preview on the dashboard | every 1.5 s | **every ~0.6 s** (`EDGE_PREVIEW_SEC=0.5`) |
| CPU / temperature | 8.1 % / 30.5 °C | **8.8 % / 31.5 °C** |

The motion gate now compares with the frame **0.5 s ago** (`MOTION_BASELINE_SEC`), not simply the previous one,
so faster sampling does not make it less sensitive (new test fails on the old gate). At the default 2 fps
behaviour is identical. Settings live in `/etc/default/edge-drone` (two lines at the end; remove them to undo).
Defaults in the code stay slow (weak radio links in the field).

**Regression found and fixed:** power showed "None" after the container started running as `eshaan`:
the Nano's power sensor files (`in_power*_input`, `rail_name_*`) are root-only. The service (root) now makes
those **read-only values** readable at every start (`ExecStartPre=-...chmod a+r`; the `-` means a failure can
never stop the service). Re-installed with `sudo jetson/install_service.sh`. Verified: power back on the dashboard (**2.58 W** at 3.75 fps, 10 % CPU, 32 °C).

**Mac:** `.link_key` added; tests: **131 Python + 70 dashboard** pass; dashboard rebuilt.

### 22. Dashboard look (laptop only: no effect on the drone's battery)
- **Drone marker:** the arrow is now a top-down **quadcopter** with 4 spinning rotors (alternating direction),
  red/green navigation lights, a forward camera cone and a pulsing scan ring. It still rotates to the course.
  Link lost → rotors stop and it greys out.
- **Alert markers:** icon pins (flame / person / smoke shapes, so colour is never the only cue) with a radar ping
  while new; clusters show the icons too.
- **Track:** soft glow under the flight line.
- **Dark mode map:** muted "tactical" basemap (darker, less saturated) so drone, track and alerts stand out.
- All animation is CSS in the browser and switches off with the OS "reduce motion" setting.
- Checked with headless Chromium at 1440x900 in dark and light: 0 console errors. 70/70 UI tests pass
  (one test updated on purpose: the dark map is now dimmer *and* desaturated).

### 23. Map accuracy bugs (found by measuring, fixed)
Measured with headless Chromium: each pin's on-screen centre vs `map.project()` of its real coordinates.

| Bug | Cause | Fix |
|---|---|---|
| **Pins up to 300 px away from their real spot**, stacked in a column (alerts with the same position showed as a line of pins down the track) | `updateAlertElement` overwrote `className`, deleting MapLibre's `maplibregl-marker` class, so pins fell back to normal page layout (`position: static`). Existed before today. | only add/remove our own `gs-amark*` classes; unit test `markers.test.ts` (failed before, passes after) |
| Pins **trailed behind the map** when dragging | my new CSS put a 0.15 s `transition` on the marker's `transform`, which MapLibre uses to position it | no transform/transition/position on marker roots |
| Hovered pin could jump | `:hover { transform: scale }` replaced MapLibre's position | the icon inside the pin scales, not the pin |

Result: pins **0.7 px** max error at rest, **0 px during a mouse drag**, drone 0.1 px, at zoom 14 and 16. 72/72 UI tests.
