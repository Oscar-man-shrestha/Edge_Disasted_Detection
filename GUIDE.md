# Complete Build & Run Guide

**Drone edge disaster detection: Jetson Nano + Lenovo USB webcam + u-blox NEO-M8N GPS + laptop ground station**

Follow this guide top to bottom, the first time and whenever you rebuild. Each step says **what to do**, **the command**, and **what you should see**. Don't move on until you see it. Tick the boxes as you go.

> Other docs: [JETSON.md](JETSON.md) (Jetson reference) · [PROJECT_STATUS.md](PROJECT_STATUS.md) (what changed and what's open) · [README.md](README.md) (overview)
> Branch: everything is on **`temp-jetson-fixes`**. Never commit directly to `main`.

---

## Contents

0. [How the whole system fits together](#0-how-the-whole-system-fits-together)
1. [What you need](#1-what-you-need)
2. [Laptop setup (and see the dashboard working in 10 minutes)](#2-laptop-setup)
3. [Prepare the Jetson Nano (flash, boot, network)](#3-prepare-the-jetson-nano)
4. [Software setup on the Nano](#4-software-setup-on-the-nano)
5. [Connect and test the hardware, one part at a time](#5-connect-and-test-the-hardware)
6. [Bring up the detection models on the Nano](#6-bring-up-the-detection-models)
7. [Field network: the Nano's own Wi-Fi hotspot](#7-field-network)
8. [The first full live run](#8-the-first-full-live-run)
9. [Make it start by itself at boot](#9-start-at-boot)
10. [Mission day checklist](#10-mission-day-checklist)
11. [After the mission: exports and report](#11-after-the-mission)
12. [Troubleshooting](#12-troubleshooting)
13. [Coding guide: where to change what](#13-coding-guide)
14. [Reference: commands, settings, ports, files](#14-reference)

---

## 0. How the whole system fits together

```
 ON THE DRONE ─────────────────────────────────────────────────────────────
  Lenovo USB webcam ──USB──┐
                           ▼
  NEO-M8N GPS ──UART──► JETSON NANO (Docker container, run_pipeline.py)
                          1. take a frame every 0.5 s
                          2. Stage 1: cheap check (fire colours / real movement)
                          3. Stage 2: YOLO (person, fire, smoke), only when Stage 1 fires
                          4. tag with GPS, save alert + snapshot (SQLite on the Nano)
                          5. link.py sends everything to the laptop:
                               status every 1 s · camera preview every 1.5 s · alerts every 2 s
                          │
                          │  Wi-Fi hotspot "DRONE-EDGE" (the Nano is 10.42.0.1)
                          ▼
 ON THE GROUND ────────────────────────────────────────────────────────────
  LAPTOP: python ground_station/app.py
     - announces itself on the Wi-Fi every 2 s, so the drone finds it (no IP typing)
     - stores everything (SQLite), serves the dashboard at http://localhost:5000
     - dashboard: live map + flight trail, camera preview, drone health,
       alerts with Acknowledge/Resolve, sounds, exports (CSV/GeoJSON/KML/report)
```

**Key ideas**
- **Adaptive compute:** the heavy YOLO models only run when the cheap Stage 1 sees something. This saves power and heat.
- **Nothing gets lost:** if the Wi-Fi drops, alerts wait on the drone and are sent when it's back.
- **No internet needed:** maps are cached on the laptop, and the dashboard has no online dependencies.

---

## 1. What you need

### Hardware checklist

| ✔ | Item | Notes |
|---|---|---|
| ☐ | Jetson Nano Developer Kit **B01** (4 GB) | ours: in the white printed case with fan and Wi-Fi antenna |
| ☐ | **5 V ⎓ 4 A power supply**, barrel plug 5.5 × 2.1 mm, centre positive | the mains lead in our box feeds this. **Check the label says 5 V.** 12 V will destroy the board. |
| ☐ | **Jumper cap** for J48 (next to the barrel jack) | without it the barrel jack doesn't power the board |
| ☐ | microSD card **64 GB** (32 GB minimum), UHS-I | for JetPack |
| ☐ | Lenovo USB webcam | open its privacy shutter |
| ☐ | u-blox **NEO-M8N** GPS puck (with compass) and its cable | we use only the GPS wires: VCC, GND, TX, RX |
| ☐ | **4 female-female jumper wires** *or* a **3.3 V USB-serial adapter** (CP2102/FTDI/CH340) | to connect the GPS (see §5.2) |
| ☐ | Multimeter | to identify the GPS wires safely |
| ☐ | For first setup only: HDMI or DP monitor, USB keyboard and mouse, Ethernet cable | after setup everything runs headless |
| ☐ | Laptop (macOS, Windows or Linux) with Wi-Fi | the ground station |

### Software checklist (laptop)

| ✔ | Item | How |
|---|---|---|
| ☐ | Python **3.9+** | python.org, or Homebrew on Mac |
| ☐ | Git | git-scm.com |
| ☐ | balenaEtcher (or Raspberry Pi Imager) | to flash the SD card |
| ☐ | Access to the GitHub repo | `https://github.com/Hisana-07/Edge_Disasted_Detection_Project` |

---

## 2. Laptop setup

### 2.1 Get the code

- [ ] Clone the repo and switch to the working branch:

```bash
git clone https://github.com/Hisana-07/Edge_Disasted_Detection_Project.git
cd Edge_Disasted_Detection_Project
git checkout temp-jetson-fixes
```

### 2.2 Python environment

- [ ] Create a virtual environment and install the dependencies.

macOS / Linux:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt pytest
```

Windows (PowerShell):
```powershell
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt pytest
```

> If you only need the **ground station** (not detection on the laptop), this is enough: `pip install flask requests opencv-python numpy pytest`.

### 2.3 Run the tests

- [ ] Run:

```bash
python -m pytest
```

**You should see:** `80 passed` (or more). No models or videos are needed for this.

### 2.4 See the full system work, without the Nano (10 minutes)

This uses the **simulated drone**. It runs the real drone code; only the camera, YOLO and sensors are simulated.

- [ ] **Terminal 1**, start the ground station:
  ```bash
  python ground_station/app.py
  ```
  **You should see:**
  ```
  Ground station on http://localhost:5000  (host <your-laptop>, 0.0.0.0)
  Beacon: UDP 5005 -> 255.255.255.255, 10.42.0.255
  ```
- [ ] **Terminal 2**, start the demo drone:
  ```bash
  python ground_station/demo_drone.py --station http://localhost:5000
  ```
  (`--station auto` also works when the laptop's broadcast reaches itself. The explicit URL always works.)
- [ ] Open **http://localhost:5000** in a browser.

**You should see, within a few seconds:**
- **LIVE · demo-drone** (green) in the top bar, plus `SIM GPS`
- the drone arrow moving on the map, with a dashed trail behind it
- the camera preview updating; after about 30 s a fire appears, the **YOLO ACTIVE** badge lights up, and alerts pop up with a sound
- alert cards on the right with **Acknowledge / Resolve / Note** buttons

- [ ] Click the 🔔 button once (browsers need one click before they allow sound).
- [ ] Stop the demo drone (Ctrl+C). Within 3–4 s the top bar turns red: **LINK LOST**.

If all of that works, your laptop side is ready.

### 2.5 Get the models and test video

The models are not in git (size and licence). Put them in `weights/`:

- [ ] **Person model (YOLOv8n):**
  ```bash
  python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"
  ```
  Then move the downloaded `yolov8n.pt` into `weights/yolov8n.pt` (`mv yolov8n.pt weights/` on Mac/Linux; drag it on Windows).
- [ ] **Fire/smoke model:** from the Hugging Face model page `seawsurf/fire_yolo`, open the *Files* tab, download **`best.pt`**, and save it as `weights/fire_smoke.pt`.
- [ ] **Test video:** any calm aerial clip, saved as `data/calm.mp4`, plus any aerial fire clip, saved as `data/test_video.mp4`. Then build the combined test video:
  ```bash
  python make_mixed_video.py data/calm.mp4 data/test_video.mp4 data/mixed_test.mp4
  ```
  **You should see:** `calm: 30.0s | fire: …s`, plus the files `data/mixed_test.mp4` and `data/mixed_test_labels.json`.
- [ ] Optional check on the laptop:
  ```bash
  python check_fire_model.py data/mixed_test.mp4
  ```
  **You should see:** `classes: {0: 'fire', 1: 'smoke'}` and detections on the fire part.

### 2.6 Cache the map for the flight area (needs internet)

The field has no internet, so save the map tiles now.

- [ ] **Easy way:** with the station running, open the dashboard and pan/zoom over your flight area once. Every tile you see is saved.
- [ ] **Explicit way:** download a box of tiles. Get the corner coordinates from Google Maps (right-click → copy coordinates):
  ```bash
  python ground_station/tiles.py prefetch --bbox 12.965,77.585,12.978,77.598 --zoom 14-18
  ```
  It refuses areas over 3000 tiles. Keep the box tight to your flight area.

---

## 3. Prepare the Jetson Nano

### 3.1 Flash JetPack 4.6

- [ ] On the laptop, download the **Jetson Nano Developer Kit SD Card Image, JetPack 4.6.x**, from NVIDIA's Jetson downloads page (JetPack archive).
- [ ] Flash it to the microSD card with **balenaEtcher**. Select the downloaded `.zip` → the SD card → Flash.
- [ ] Insert the card into the slot **under the heatsink module**, on the back edge of the Nano.

### 3.2 Power: get this right first

- [ ] Fit the **jumper on J48**, the 2-pin header next to the barrel jack. This switches power input from micro-USB to the barrel jack.
- [ ] Check the power brick label: **5 V, at least 4 A**.
- [ ] The fan in our case is wired to the 40-pin header (5 V/GND). Note which pins it uses; you need free pins for the GPS in §5.2.

### 3.3 First boot (monitor, keyboard and Ethernet attached)

- [ ] Connect the HDMI monitor, keyboard, mouse and **Ethernet** (it needs internet for setup). Then plug in the 5 V barrel jack.
- [ ] Complete the Ubuntu setup wizard: language, user name, password, timezone. Choose **MAXN** if it asks about the power mode.
- [ ] Note your username. This guide writes it as `<user>`.

### 3.4 Network and SSH

- [ ] On the Nano, find its IP address:
  ```bash
  hostname -I
  ```
- [ ] From the laptop (same network), check you can SSH in:
  ```bash
  ssh <user>@<nano-ip>
  ```
  From now on you can run everything from the laptop over SSH, and the monitor and keyboard can go.

> **Important ordering:** do all of §4 (it downloads several GB) **while the Nano has internet** over Ethernet or home Wi-Fi. Turn on the field hotspot (§7) only after that, because the hotspot takes over the Wi-Fi card.

---

## 4. Software setup on the Nano

All commands in this section run **on the Nano** (over SSH).

### 4.1 Get the code

- [ ] Run:

```bash
git clone https://github.com/Hisana-07/Edge_Disasted_Detection_Project.git
cd Edge_Disasted_Detection_Project
git checkout temp-jetson-fixes
```

### 4.2 One-time setup script

- [ ] Run:

```bash
jetson/setup_nano.sh
```

It asks for your password (sudo). **You should see** a list of `OK` / `WARN` lines:

| Line | Meaning if it's WARN |
|---|---|
| Board / model | not a Jetson, or not JetPack 4 |
| Power mode | `nvpmodel` missing |
| Docker + NVIDIA runtime | install `docker.io nvidia-container-runtime` |
| Swap | it creates 4 GB of swap automatically (needed for TensorRT) |
| Build edge-drone image | **this takes a while** (it downloads several GB) |
| Files that are not in git | you still need to copy the models (next step) |
| Camera | plug the webcam in (§5.1) |
| Flight-controller UART | `nvgetty` still owns the UART (§5.2) |

### 4.3 Copy models and test video from the laptop

- [ ] **On the laptop**, from the repo folder:

```bash
scp weights/yolov8n.pt weights/fire_smoke.pt <user>@<nano-ip>:~/Edge_Disasted_Detection_Project/weights/
scp data/mixed_test.mp4 data/mixed_test_labels.json <user>@<nano-ip>:~/Edge_Disasted_Detection_Project/data/
```

### 4.4 How you run things on the Nano

Everything runs **inside Docker** through one helper script, from the repo folder:

```bash
jetson/run_docker.sh python3 <script>.py      # run a script in the container
jetson/run_docker.sh                          # open a shell in the container
```

- Any `EDGE_*` or `GS_*` variable you put in front is passed into the container, e.g. `EDGE_DEVICE=0 jetson/run_docker.sh python3 benchmark.py`.
- The webcam (`/dev/video*`) and the serial ports (`/dev/ttyTHS1`, `/dev/ttyUSB*`) are passed in automatically if they exist.

---

## 5. Connect and test the hardware

Connect **one part at a time** and test it before the next. **Always power off the Nano before wiring the 40-pin header:** `sudo poweroff`, then unplug the power.

### 5.1 Lenovo USB webcam

- [ ] Plug it into any blue USB 3.0 port. **Slide the privacy shutter open.**
- [ ] Check Linux sees it (on the Nano):
  ```bash
  ls /dev/video*
  ```
  **You should see:** `/dev/video0`
- [ ] Optional, see which modes it supports:
  ```bash
  sudo apt install -y v4l-utils && v4l2-ctl --list-formats-ext -d /dev/video0
  ```
  Look for **MJPG 1280x720**. That's what `config.py` asks for.
- [ ] Grab a test frame inside the container:
  ```bash
  jetson/run_docker.sh python3 -c "import cv2; c=cv2.VideoCapture(0); c.read(); ok,f=c.read(); print(ok, f.shape); cv2.imwrite('data/cam_test.jpg', f)"
  ```
  **You should see:** `True (720, 1280, 3)` or similar. Copy `data/cam_test.jpg` to the laptop and check it's not black.

### 5.2 NEO-M8N GPS

**Step 1: identify the wires (safety first).** The GPS cable's colours and order **differ between sellers**. Look for labels on the GPS module's PCB (VCC, GND, TX, RX). If there are none, use the multimeter with the GPS powered from a 5 V source: GND–VCC reads about 5 V, and the TX line idles at about 3.3 V. **Don't guess:** 5 V on a Nano data pin will damage it.

**Step 2: choose a connection.**

**Option A: USB-serial adapter (easiest and safest).** Set the adapter's jumper to 3.3 V if it has one.

| GPS wire | Adapter pin |
|---|---|
| VCC | 5V |
| GND | GND |
| TX | **RX** |
| RX | **TX** |

Plug the adapter into the Nano. It appears as `/dev/ttyUSB0`, so use `EDGE_GPS_PORT=/dev/ttyUSB0` everywhere below.

**Option B: directly on the Nano's 40-pin header (`/dev/ttyTHS1`).**

```
   Nano 40-pin header, J41 (pin numbers are printed on the board)
        3V3  (1) (2)  5V    ◄── GPS VCC     (or pin 4 if pin 2 is used by the fan)
             (3) (4)  5V
             (5) (6)  GND   ◄── GPS GND     (or pin 9 / 14 if pin 6 is used by the fan)
             (7) (8)  UART TX ──► GPS RX
        GND  (9) (10) UART RX ◄── GPS TX
```

| GPS wire | Nano pin |
|---|---|
| VCC | **2** (5 V); or 4 if the fan uses 2 |
| GND | **6**; or 9 or 14 if the fan uses 6 |
| TX | **10** (UART RX) |
| RX | **8** (UART TX) |

> TX always goes to RX, crossed over. The Nano's UART pins are **3.3 V only**. The compass's 4-pin plug stays unconnected.

**Step 3: free the UART (Option B only, once).**

- [ ] Run:

```bash
sudo systemctl disable --now nvgetty
sudo usermod -aG dialout $USER        # then log out and back in
```

**Step 4: test it outdoors, or at a window with open sky.**

- [ ] Run:

```bash
EDGE_GPS=nmea EDGE_GPS_PORT=/dev/ttyTHS1 jetson/run_docker.sh python3 gps_source.py
```

(Use `/dev/ttyUSB0` for Option A.)

**You should see:**
```
[gps] nmea /dev/ttyTHS1 @ 9600 baud (fix comes later if the sky view is poor)
Ctrl+C to stop
no fix  sats=3 hdop=None sentences=12
...
12.97xxxx, 77.59xxxx  sats=9 hdop=0.9 sentences=240
```

- The first fix takes 30 s to a few minutes from cold. The module's LED usually starts blinking once it has a fix.
- `no NMEA data ...` means the wiring is wrong (TX/RX swapped), it has no power, or `nvgetty` is still on.
- `sentences` going up but `no fix` means the wiring is fine; it just needs a clearer view of the sky.

### 5.3 Power sensor

- [ ] Run:

```bash
jetson/run_docker.sh python3 power_monitor.py
```

**You should see:** `power source: sysfs:POM_5V_IN` and `idle: ~1500–2500 mW`.

---

## 6. Bring up the detection models

Run these in order on the Nano. Use full performance mode first: `sudo nvpmodel -m 0 && sudo jetson_clocks`.

| # | ✔ | Command | You should see |
|---|---|---|---|
| 1 | ☐ | `EDGE_DEVICE=0 jetson/run_docker.sh python3 check_fire_model.py data/mixed_test.mp4` | `classes: {0: 'fire', 1: 'smoke'}`, then detection lines |
| 2 | ☐ | `EDGE_DEVICE=0 jetson/run_docker.sh python3 benchmark.py --tag nano_pytorch` | a results table, `saved data/benchmark_nano_pytorch.json`, energy numbers |
| 3 | ☐ | `jetson/run_docker.sh python3 export_trt.py` | `wrote weights/yolov8n.engine` and `weights/fire_smoke.engine` (several minutes each) |
| 4 | ☐ | `EDGE_DEVICE=0 EDGE_PERSON_WEIGHTS=weights/yolov8n.engine EDGE_FIRE_WEIGHTS=weights/fire_smoke.engine jetson/run_docker.sh python3 benchmark.py --tag nano_trt` | `data/benchmark_nano_trt.json`, with Stage 2 much faster than in #2 |

**If step 1 fails** with an unknown module or layer error, the container's Ultralytics is too old for the YOLO26 fire model. Rebuild the image with a newer one:
```bash
sudo docker build --build-arg UPGRADE_ULTRALYTICS=1 -t edge-drone jetson/
```
If it still fails, export to ONNX **on the laptop** (`python export_onnx.py`), copy `weights/fire_smoke.onnx` to the Nano, and use `EDGE_FIRE_WEIGHTS=weights/fire_smoke.onnx`.

Keep both benchmark JSON files: they're the main results of the project, comparing PyTorch and TensorRT on time and energy.

---

## 7. Field network

In the field there's no router: the Nano creates its own Wi-Fi network.

- [ ] **Finish §4 and §6 first** (they need internet).
- [ ] On the Nano:
  ```bash
  sudo jetson/hotspot.sh
  ```
  **You should see:**
  ```
  hotspot up: SSID 'DRONE-EDGE' on wlan0, Nano at 10.42.0.1, starts at boot
  password (shown once, write it down): XXXXXXXXXXXX
  ```
  To choose your own password: `sudo jetson/hotspot.sh --password 'something-long'`.
- [ ] **Write the password down.** The hotspot now comes up at every boot.
- [ ] On the laptop, join the Wi-Fi network **DRONE-EDGE**.
- [ ] Check you can reach the Nano: `ssh <user>@10.42.0.1`
- [ ] **Allow the station through the laptop firewall** (once):
  - **macOS:** the first time you run `python ground_station/app.py`, click **Allow** on "accept incoming network connections". Or go to System Settings → Network → Firewall → Options → allow Python.
  - **Windows:** on the Defender prompt, tick **Private networks** → Allow. When Windows asks, choose "Private" for the DRONE-EDGE network.
- [ ] To get normal Wi-Fi back on the Nano later: `sudo jetson/hotspot.sh --off`.

> If `hotspot.sh` says the Wi-Fi card has no AP mode, use a phone hotspot that both the Nano and the laptop join. Discovery works the same way.

---

## 8. The first full live run

### 8.1 Start the ground station (laptop, joined to DRONE-EDGE)

- [ ] Run:

```bash
source venv/bin/activate           # Windows: venv\Scripts\Activate.ps1
python ground_station/app.py
```

Then open **http://localhost:5000**. The top bar says **WAITING FOR DRONE**.

### 8.2 Start the pipeline (Nano, over SSH to 10.42.0.1)

- [ ] Run:

```bash
cd ~/Edge_Disasted_Detection_Project
EDGE_DEVICE=0 EDGE_SOURCE=0 EDGE_GPS=nmea EDGE_GPS_PORT=/dev/ttyTHS1 \
EDGE_PERSON_WEIGHTS=weights/yolov8n.engine EDGE_FIRE_WEIGHTS=weights/fire_smoke.engine \
jetson/run_docker.sh python3 run_pipeline.py
```

**You should see on the Nano:**
```
[gps] nmea /dev/ttyTHS1 @ 9600 baud ...
[link] station: auto (waiting for the ground station beacon on UDP 5005)
[camera] usb 1280x720 @ 30 fps
[link] ground station found at http://10.42.0.xx:5000
```

**You should see on the dashboard within about 2 s:**

| Element | Expected |
|---|---|
| Top bar | **LIVE · `<nano hostname>`** (green), GPS `FIX · N sats` (or `NO FIX` indoors) |
| Live camera | the webcam image refreshing about every 1.5 s |
| Status cards | pipeline SCANNING, frame rate ~2 fps, board power in W, CPU/GPU temperatures |
| Map | drone arrow at your position (once GPS has a fix) |

### 8.3 Test detection indoors

- [ ] Play a fire video on a phone or monitor and point the webcam at it.
- [ ] **You should see:** the pipeline goes to **ACTIVE**, the **YOLO ACTIVE** badge lights up, a **fire alert** pops up with a beep, and a card appears with a snapshot.
- [ ] Indoors the alert says **no GPS fix**. That's expected; outdoors it has coordinates.
- [ ] Click **Acknowledge**, then **Resolve**. The card and map marker update.

### 8.4 Test the link recovery

- [ ] Walk the laptop out of Wi-Fi range (or turn its Wi-Fi off for 20 s). The dashboard shows **LINK LOST**.
- [ ] Trigger a detection meanwhile. The "Alerts waiting on drone" card counts up once you're back.
- [ ] Reconnect. Within a few seconds the waiting alerts arrive. **Nothing is lost.**

### 8.5 Stop

- [ ] Press Ctrl+C on the Nano. **You should see:** `[stop] stopping, flushing alerts`, then a summary table.

---

## 9. Start at boot

Once §8 works, make the drone start by itself with no monitor attached:

- [ ] Run:

```bash
sudo jetson/install_service.sh
sudo nano /etc/default/edge-drone      # check EDGE_GPS_PORT; EDGE_SERVER_URL=auto finds the laptop
sudo systemctl start edge-drone
journalctl -u edge-drone -f            # live log, Ctrl+C to leave
```

From now on, powering the Nano does this by itself: hotspot up → max clocks → pipeline running → it finds the laptop.

To turn it off: `sudo systemctl disable --now edge-drone`.

---

## 10. Mission day checklist

**At home, with internet, the day before**
- [ ] Map tiles cached for the flight area (§2.6)
- [ ] `git pull` on the laptop and the Nano (same branch)
- [ ] Laptop and drone batteries charged
- [ ] Hotspot password written down

**On site, before take-off**
- [ ] J48 jumper on, 5 V 4 A supply or battery connected, **fan spinning**
- [ ] Webcam **shutter open**, lens clean, mounted pointing down or forward as planned
- [ ] GPS puck on top with a clear sky view
- [ ] Laptop joined **DRONE-EDGE**, `python ground_station/app.py` running, dashboard open
- [ ] Top bar: **LIVE** and **FIX · ≥ 6 sats**
- [ ] Camera preview updating
- [ ] Test detection: show a fire image on a phone to the camera → alert + beep
- [ ] Sound on (🔔), and click **New mission** with a name (e.g. `Site A – 12 Nov`)

**During the flight**
- [ ] Watch for **LINK LOST**. Alerts are kept on the drone and arrive when it's back in range.
- [ ] **Acknowledge** alerts as the team responds, and **Resolve** them when handled, adding a **Note** (e.g. "team 2 dispatched")

**After landing**
- [ ] Check "Alerts waiting on drone" shows **0** before powering off
- [ ] Export (§11)

---

## 11. After the mission

From the dashboard's **Export ▾** menu (for the current mission):

| Export | Use it for |
|---|---|
| **CSV** | Excel / Google Sheets |
| **GeoJSON** | QGIS or other GIS tools: alerts as points, flight track as a line |
| **KML** | **Google Earth**: coloured placemarks plus the flight track |
| **Printable report** | summary, counts, first-detection times, distance flown, table with snapshots. Use **Print → Save as PDF**. |

The station keeps everything in `ground_station/received/` (database, snapshots and map tiles). Back that folder up after important missions.

---

## 12. Troubleshooting

| Symptom | Fix |
|---|---|
| Nano resets or shuts off when YOLO starts | power: 5 V **4 A** barrel jack plus the **J48 jumper**. Micro-USB can't keep up. |
| Nano won't power on from the barrel jack | J48 jumper missing |
| `Could not open source: 0` | webcam unplugged, or `/dev/video0` missing on the host (`ls /dev/video*`) |
| Preview is black | webcam privacy shutter closed |
| `no NMEA data on /dev/ttyTHS1` | TX/RX not crossed, GPS not powered, or `nvgetty` still enabled (§5.2 step 3) |
| GPS stuck at `no fix` | indoors or no sky view. Go outside and wait up to 3 min. |
| Dashboard stuck on **WAITING FOR DRONE** | laptop not on DRONE-EDGE; laptop firewall blocking Python (§7); Nano log lacks `[link] ground station found`. Workaround: `EDGE_SERVER_URL=http://<laptop-ip>:5000` on the Nano. Test from the Nano: `curl http://<laptop-ip>:5000/health`. |
| **LINK LOST** during flight | out of Wi-Fi range or the pipeline stopped. Alerts are buffered and arrive later. |
| Map is grey or blank in the field | the tiles weren't cached. Redo §2.6 at home. |
| No alert sound | click 🔔 once (browsers block sound until you interact with the page) |
| `check_fire_model.py` fails on the Nano | YOLO26 / old Ultralytics: see the fallbacks under §6 |
| TensorRT export killed | out of memory: rerun `jetson/setup_nano.sh` (swap) and close the desktop session |
| Everything is slow | `sudo nvpmodel -m 0 && sudo jetson_clocks` (the boot service does this for you) |
| Board very hot (cards show WARM/HOT) | check the fan is spinning; HOT is ≥ 80 °C |
| Station says `bad link key` (401) | `GS_LINK_KEY` on the laptop and `EDGE_LINK_KEY` on the Nano must match (or leave both unset) |

---

## 13. Coding guide

### 13.1 Where things live

| You want to change… | File |
|---|---|
| Any setting or threshold | `config.py` (environment variables override some, see §14) |
| How a frame is taken (camera, video, rate, size) | `frame_source.py` |
| The cheap Stage 1 check (fire colours, motion compensation) | `stage1_gate.py` |
| YOLO models and how often they run | `stage2_detector.py` (`Stage2Detector`, `Stage2Scheduler`) |
| Which detections become alerts (cooldown, person threshold, priority) | `alert_store.py` |
| GPS (sim / NMEA M8N / MAVLink) | `gps_source.py`, `gps_sim.py` |
| What the drone sends to the station, and how often | `link.py`, `system_stats.py` |
| The main loop | `run_pipeline.py` |
| Station API and storage | `ground_station/app.py`, `ground_station/store.py` |
| Dashboard look and behaviour | `ground_station/templates/index.html`, `static/app.css`, `static/app.js` |
| Exports and report | `ground_station/exports.py`, `templates/report.html` |
| Jetson scripts (Docker, setup, hotspot, autostart) | `jetson/` |

### 13.2 Common changes

- **Tune Stage 1 for your footage:** run `python test_stage1.py` on a video, then adjust `FIRE_HSV_*`, `FIRE_PIXEL_FRACTION` and `DIFF_FRACTION` in `config.py`.
- **Make YOLO run more or less often during a fire:** set `EDGE_STAGE2_EVERY_N` (`1` = every frame, `3` = default).
- **Change alert sensitivity:** `CONF_THRESHOLD` (all detections), `PERSON_ALERT_CONF` (people), `ALERT_COOLDOWN_SEC`.
- **Add a new detection type** (e.g. "flood"):
  1. Train or obtain a YOLO model and load it in `Stage2Detector`.
  2. Add it to `PRIORITY` in `alert_store.py` **and** `ground_station/app.py`.
  3. Add it to `TYPES` in `ground_station/exports.py` and `static/app.js` (`PRIORITY`, `TYPES`, `LETTER`).
  4. Add a colour in `static/app.css`. Pick one that stays distinguishable from blue, orange and aqua.
  5. Add tests.
- **Change how often the drone reports:** `TELEMETRY_INTERVAL_SEC`, `PREVIEW_INTERVAL_SEC` and `ALERT_FORWARD_INTERVAL_SEC` in `config.py`.

### 13.3 How we work

1. Pull first: `git pull`, on branch `temp-jetson-fixes` or a new `temp-*` branch. **Never push to `main`** without the team agreeing.
2. Write or adjust a test in `tests/` first, then the code.
3. `python -m pytest`: everything must pass.
4. Check your change on the dashboard with `demo_drone.py` (§2.4) before testing on the Nano.
5. Commit with a clear message, then push your branch.
6. Drone-side code must stay **Python 3.8 compatible** (the JetPack 4 container): no `match`, no `list[int]` type hints, no `X | Y` types.

### 13.4 Test files

| Test file | Covers |
|---|---|
| `tests/test_stage1_gate.py` | Stage 1, including motion compensation |
| `tests/test_scheduler.py` | Stage 2 scheduler |
| `tests/test_gps*.py` | GPS sim and NMEA (including a fake serial port) |
| `tests/test_link.py` | drone link, discovery, and `run_pipeline.py` end to end |
| `tests/test_gs_*.py` | station store, API, live updates, exports, tiles |
| `tests/test_power_monitor.py`, `tests/test_system_stats.py` | Jetson sensors |

---

## 14. Reference

### Commands cheat sheet

| Where | Command | What |
|---|---|---|
| laptop | `python ground_station/app.py` | ground station + dashboard (http://localhost:5000) |
| laptop | `python ground_station/demo_drone.py --station http://localhost:5000` | simulated drone |
| laptop | `python ground_station/tiles.py prefetch --bbox lat1,lon1,lat2,lon2 --zoom 14-18` | cache map tiles |
| laptop | `python -m pytest` | all tests |
| laptop | `python export_onnx.py` | ONNX fallback models |
| Nano | `jetson/setup_nano.sh` | one-time setup |
| Nano | `jetson/run_docker.sh python3 run_pipeline.py` | the drone pipeline |
| Nano | `jetson/run_docker.sh python3 gps_source.py` | GPS test |
| Nano | `jetson/run_docker.sh python3 power_monitor.py` | power sensor test |
| Nano | `jetson/run_docker.sh python3 benchmark.py --tag NAME` | benchmark (time + energy) |
| Nano | `jetson/run_docker.sh python3 export_trt.py` | build TensorRT engines |
| Nano | `jetson/run_docker.sh python3 forward_now.py` | push buffered alerts now |
| Nano | `sudo jetson/hotspot.sh` / `--off` | field Wi-Fi on/off |
| Nano | `sudo jetson/install_service.sh` | start at boot |
| Nano | `journalctl -u edge-drone -f` | live log of the boot service |

### Settings (environment variables)

| Variable | Default | Meaning |
|---|---|---|
| `EDGE_SOURCE` | `data/mixed_test.mp4` | `0` = USB webcam, a video path, `csi`, or an MJPEG URL |
| `EDGE_DEVICE` | `cpu` | `0` = Jetson GPU |
| `EDGE_PERSON_WEIGHTS` / `EDGE_FIRE_WEIGHTS` | `weights/*.pt` | `.pt`, `.engine` (TensorRT) or `.onnx` |
| `EDGE_GPS` | `sim` | `nmea` for the M8N, `sim` for the simulated path, `mavlink` for a flight controller |
| `EDGE_GPS_PORT` / `EDGE_GPS_BAUD` | `/dev/ttyTHS1` / `0` (auto) | GPS serial port |
| `EDGE_SERVER_URL` | `auto` | finds the station automatically; or `http://<laptop-ip>:5000` |
| `EDGE_DRONE_ID` | hostname | name shown on the dashboard |
| `EDGE_LINK_KEY` | none | shared key, must equal `GS_LINK_KEY` |
| `EDGE_MOTION_COMP` | `1` | Stage 1 motion compensation |
| `EDGE_STAGE2_EVERY_N` | `3` | YOLO frequency while a detection is confirmed |
| `EDGE_DB_PATH` | `data/alerts.db` | drone alert buffer |
| `GS_HOST` / `GS_PORT` | `0.0.0.0` / `5000` | station address (`127.0.0.1` = this laptop only) |
| `GS_DATA_DIR` | `ground_station/received` | station database, snapshots and map tiles |
| `GS_LINK_KEY` | none | key the drone must send |
| `GS_BEACON_TARGETS` / `GS_BEACON_PORT` | `255.255.255.255,10.42.0.255` / `5005` | where the station announces itself |

### Ports

| Port | Protocol | Direction | Used for |
|---|---|---|---|
| 5000 | TCP | Nano → laptop | alerts, status updates, previews; the dashboard in the browser |
| 5005 | UDP broadcast | laptop → Wi-Fi | station beacon (auto-discovery) |
| 8090 | TCP | on the Nano only | optional CSI camera bridge |

### Where data is stored

| Where | What |
|---|---|
| Nano `data/alerts.db` | alert buffer (`sent=0` means still waiting for the link) |
| Nano `data/snapshots/` | alert snapshots with boxes |
| Nano `data/benchmark_*.json` | benchmark results |
| Laptop `ground_station/received/station.db` | all missions, alerts, notes and the flight track |
| Laptop `ground_station/received/snaps/` | snapshots received from the drone |
| Laptop `ground_station/received/tiles/` | cached map tiles |
