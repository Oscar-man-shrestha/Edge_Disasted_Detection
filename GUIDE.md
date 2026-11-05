# Drone Disaster Detection: Build & Run Guide, from Zero

This guide takes you from a box of parts to a working drone that spots **fire, smoke and people** and shows them live on a laptop, with **no internet**.

**How to use it**
- Do the steps **in order**. Every step has the same parts:
  - **Do** what to do
  - **Run** the command
  - **✅ Check** what you should see
- Don't move on until the ✅ matches. If it doesn't, the [Troubleshooting](#troubleshooting) table at the end has the fix.
- Commands marked **(laptop)** run on your laptop. Commands marked **(Nano)** run on the Jetson, usually over SSH.

> **Branch:** everything is on **`temp-jetson-fixes`**. Never commit to `main`.
> Other docs: [JETSON.md](JETSON.md) (Jetson reference), [PROJECT_STATUS.md](PROJECT_STATUS.md) (what changed and what's open).

---

## Overview: the steps

| Part | Steps | You end with |
|---|---|---|
| A. Understand & check your parts | 1–3 | everything on the table, missing items ordered |
| B. Laptop & dashboard | 4–10 | the dashboard running with a simulated drone |
| C. Jetson Nano: power, flash, boot | 11–16 | the Nano booted, reachable over SSH |
| D. Nano software | 17–19 | Docker image built, models copied |
| E. Connect the parts, one at a time | 20–26 | webcam, GPS and power sensor all tested |
| F. Detection models on the Nano | 27–30 | models run on the GPU (TensorRT) |
| G. Field Wi-Fi | 31–34 | the laptop talks to the Nano with no router |
| H. First full live run | 35–39 | real alerts on the laptop map |
| I. Start at boot & mount on the drone | 40–44 | a flight-ready drone |
| J. Mission day & afterwards | 45–47 | a mission flown, reviewed, exported |

---

# Part A: Understand and check your parts

### Step 1: See how it all fits together

```
 ON THE DRONE ──────────────────────────────────────────────────────────────────────
   Lenovo USB webcam ──USB──────────┐
                                     ▼
   NEO-M8N GPS puck ──4 wires──► JETSON NANO B01  (white case, fan, Wi-Fi antenna)
                                  │  every 0.5 s: take a picture
                                  │  Stage 1: cheap check (fire colours / real movement)
                                  │  Stage 2: YOLO AI (person / fire / smoke), only when Stage 1 fires
                                  │  tag with GPS, save alert + photo (kept until delivered)
   5 V 4 A power ──barrel jack──►│
                                  ▼  own Wi-Fi network "DRONE-EDGE"
 ON THE GROUND ─────────────────────────────────────────────────────────────────────
   LAPTOP: python ground_station/app.py   →  http://localhost:5050
     Live      live map (2D/3D), drone position and heading, camera picture, drone health,
               alerts with sound, Acknowledge / Resolve
     Replay    replay the whole flight on a timeline
     Analytics charts: detections, power, temperatures, compute saved
     Missions  every flight, with reports and exports (CSV, Google Earth KML, PDF)
```

**Three ideas to remember**
- **Saves power:** the heavy AI only runs when the cheap check sees something.
- **Never loses alerts:** if Wi-Fi drops, alerts wait on the drone and are sent when it's back.
- **No internet needed:** maps are saved on the laptop beforehand, and the drone finds the laptop by itself.

### Step 2: Check the parts you have

**Do:** lay everything out and tick it off.

| ✔ | Part (what you have) | Notes |
|---|---|---|
| ☐ | **Jetson Nano Developer Kit B01** in the white case, with a black **40 mm fan** (red/black wires go to the pin header) and a **Wi-Fi antenna** (gold screw connector) | the "brain" |
| ☐ | **Lenovo USB webcam** (silver, with a privacy slider next to the lens) | the eye |
| ☐ | **NEO-M8N "GPS module with compass"** (round black puck) | position |
| ☐ | **GPS cables:** a **6-pin** plug (GPS) and a **4-pin** plug (compass) | we use only 4 GPS wires: VCC, GND, TX, RX |
| ☐ | **Black mains lead with a 2-pin plug** | this goes into a power brick; it is not the Nano's power by itself |

### Step 3: Get the missing pieces

| ✔ | Buy or borrow | Why |
|---|---|---|
| ☐ | **5 V ⎓ 4 A power supply**, barrel plug **5.5 × 2.1 mm**, centre positive | Nano power. ⚠️ **The label must say 5 V.** 12 V destroys the board. |
| ☐ | **Jumper cap** (2-pin, 2.54 mm) for **J48** | without it the barrel jack doesn't power the Nano |
| ☐ | **microSD card, 64 GB** (32 GB minimum), A1/U3 | holds the Nano's operating system |
| ☐ | **4 female-female jumper wires** *or* a **3.3 V USB-serial adapter** (CP2102 / FTDI / CH340) | to connect the GPS. The adapter is easier and safer. |
| ☐ | **Multimeter** | to identify the GPS wires safely |
| ☐ | For setup only: HDMI monitor, USB keyboard and mouse, **Ethernet cable** | after setup the Nano runs headless |
| ☐ | For flying: a **5 V ≥ 4 A UBEC/BEC** (a voltage regulator) from the drone battery, plus a barrel plug | see Step 43 |
| ☐ | A laptop with Wi-Fi (macOS, Windows or Linux) | the ground station |

---

# Part B: Laptop and dashboard (no Nano needed yet)

### Step 4: Install the basics (laptop)

**Do:** install **Python 3.9+** (python.org), **Git** (git-scm.com) and **balenaEtcher** (balena.io/etcher).

**✅ Check:**
```bash
python3 --version
```
```bash
git --version
```
The first shows Python 3.9 or newer.

### Step 5: Get the code (laptop)

**Run:**
```bash
git clone https://github.com/Hisana-07/Edge_Disasted_Detection_Project.git
cd Edge_Disasted_Detection_Project
git checkout temp-jetson-fixes
```
**✅ Check:** `git branch --show-current` prints `temp-jetson-fixes`.

### Step 6: Python environment (laptop)

**Run (macOS / Linux):**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt pytest
```
**Run (Windows PowerShell):**
```powershell
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt pytest
```
**✅ Check:** the prompt starts with `(venv)`.

> Every new terminal needs the `activate` line again.

### Step 7: Run the tests (laptop)

**Run:**
```bash
python -m pytest
```
**✅ Check:** about `110 passed` at the end. No models or hardware are needed for this.

### Step 8: Start the ground station and a simulated drone (laptop)

**Terminal 1, run:**
```bash
python ground_station/app.py
```
**✅ Check:**
```
Ground station on http://localhost:5050  (host <your-laptop>, 0.0.0.0)
Beacon: UDP 5005 -> 255.255.255.255, 10.42.0.255
```

**Terminal 2** (activate the venv first), **run:**
```bash
python ground_station/demo_drone.py --station http://localhost:5050
```
**✅ Check:** `demo drone 'demo-drone': station=http://localhost:5050 …`. After about 30 s it prints `ALERT #1 fire …`.

> The demo runs the **real drone code**; only the camera, AI and sensors are simulated. Use it any time you want to demo the system without the Nano.

### Step 9: Tour the dashboard (laptop)

**Do:** open **http://localhost:5050** in Chrome, Edge or Firefox. Click the 🔔 bell once (browsers only allow sound after one click).

**✅ Check, in the Live view (default):**
- [ ] The top bar shows **LIVE · demo-drone** in green, `SIM GPS`, the mission timer, and alert counters (person / fire / smoke).
- [ ] On the **map**, the drone arrow glides along a blue gradient trail.
- [ ] **Left:** a **Camera** card with the live picture, and a **Flight** panel (compass, speed, power gauge, CPU/GPU temperature, frame-rate and power sparklines).
- [ ] After about 30 s the fire appears: the camera shows **YOLO ACTIVE**, a pop-up and beep arrive, and **person** alerts bring up a **red banner**.
- [ ] **Right:** the **Alerts** drawer. Click an alert to see its photo, then **Acknowledge**, **Resolve** and **Reopen**, and add a **note**.
- [ ] Map buttons (right edge): **2D/3D** (or press `3`), follow-drone, heading-up, fit-all, and layers.

**✅ Check the other views** (left rail; bottom tabs on a phone):
- [ ] **Replay:** press ▶ and switch between 1× / 4× / 16×. Coloured ticks on the timeline are alerts; click one to jump to it.
- [ ] **Analytics:** headline numbers (alerts, duration, distance, **compute saved**, power, peak temperatures) and charts. The **Table** tab shows the raw data.
- [ ] **Missions:** every mission with Replay / Analytics / **Report** (print → save as PDF) / CSV / GeoJSON / KML.
- [ ] Press **⌘K** (Mac) or **Ctrl+K** (Windows) for the command palette, and **?** for all shortcuts. The ☀/☾ button switches light/dark.
- [ ] Stop the demo drone (Ctrl+C in terminal 2). **✅** Within about 3 s the top bar turns red: **LINK LOST · N s**.

🎉 The ground station works. Keep terminal 1 open for the next step.

### Step 10: Get the AI models, test video and offline map (laptop, needs internet)

**Do 1: the person model.**
```bash
python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"
```
Then move the downloaded `yolov8n.pt` into `weights/` (Mac/Linux: `mv yolov8n.pt weights/`).

**Do 2: the fire/smoke model.** On Hugging Face, open the model page **`seawsurf/fire_yolo`**, go to *Files*, open the **`weights/`** folder, download **`best.pt`** (5.4 MB), and save it as **`weights/fire_smoke.pt`**. Direct link: `https://huggingface.co/seawsurf/fire_yolo/resolve/main/weights/best.pt`.

**Do 3: the test video.** Save any calm aerial clip as `data/calm.mp4` and any aerial fire clip as `data/test_video.mp4`. Then:
```bash
python make_mixed_video.py data/calm.mp4 data/test_video.mp4 data/mixed_test.mp4
```
**✅ Check:** `data/mixed_test.mp4` and `data/mixed_test_labels.json` exist.

**Do 4 (optional): check the fire model on the laptop.**
```bash
python check_fire_model.py data/mixed_test.mp4
```
**✅ Check:** `classes: {0: 'fire', 1: 'smoke'}`, plus detection lines.

**Do 5: save the map of your flight area for offline use.** Find the area's corners in Google Maps (right-click → copy coordinates). **Run** (keep the box tight):
```bash
python ground_station/tiles.py prefetch --bbox 12.965,77.585,12.978,77.598 --zoom 14-18 --terrain
```
**✅ Check:** `… tiles in area (map + terrain) …`, then `downloaded N tiles`. It refuses more than 3000 tiles; shrink the box if it does. The easy alternative: with the station running, pan and zoom the dashboard map over the area (all tiles you see are saved), and press `3` to save the 3D terrain too.

---

# Part C: Jetson Nano: power, flash, first boot

### Step 11: Flash the microSD card (laptop)

**Do:**
1. On NVIDIA's Jetson download page (JetPack archive), download the **Jetson Nano Developer Kit SD Card Image, JetPack 4.6.x**.
2. Open **balenaEtcher**, then **Flash from file** (the downloaded `.zip`), **Select target** (your microSD) and **Flash**.

**✅ Check:** Etcher says *Flash Complete*.

### Step 12: Insert the card

**Do:** the microSD slot is **under the black heatsink module**, at the back edge of the board. Push the card in, contacts up, until it clicks.

### Step 13: Set up power safely

**Do:**
1. Put the **jumper cap on J48**, the 2-pin header right next to the barrel jack.
2. Check the brick's label says **5 V and 4 A or more**. Plug the black mains lead into the brick, not into the Nano.
3. Look at the **fan's red/black wires** on the 40-pin header and note which pins they use (usually a 5 V pin and a GND pin). You need other free pins for the GPS in Step 23.

> ⚠️ Micro-USB power (5 V 2 A) can boot the Nano, but it **resets when the AI runs**. Always use the barrel jack and J48 jumper.

### Step 14: First boot (monitor, keyboard, Ethernet attached)

**Do:** connect HDMI, keyboard, mouse and **Ethernet** (it needs internet for setup), then plug in the barrel jack.

**✅ Check:**
- the green LED near the micro-USB port lights up
- the fan spins
- the Ubuntu setup wizard appears

### Step 15: Complete the setup wizard

**Do:** accept the licence, choose language, keyboard and timezone, then create your **user name and password** (written as `<user>` below). If it asks about the power mode, pick **MAXN**.

**✅ Check:** you reach the Ubuntu desktop.

### Step 16: Connect from the laptop over SSH

**Run (Nano, in a terminal on its desktop):**
```bash
hostname -I
```
Note the first address (e.g. `192.168.1.57`). That's `<nano-ip>`.

**Run (laptop):**
```bash
ssh <user>@<nano-ip>
```
**✅ Check:** you get a prompt like `<user>@<nano-name>:~$`. From now on, run the Nano commands over this SSH session. The monitor and keyboard can be unplugged.

> ⚠️ **Do Parts D and F while the Nano has internet** (Ethernet). The field hotspot in Part G takes over the Wi-Fi card.

---

# Part D: Nano software

### Step 17: Get the code (Nano)

**Run:**
```bash
git clone https://github.com/Hisana-07/Edge_Disasted_Detection_Project.git
cd Edge_Disasted_Detection_Project
git checkout temp-jetson-fixes
```

### Step 18: One-time setup script (Nano)

**Run:**
```bash
jetson/setup_nano.sh
```
It asks for your password. **It takes a while**, because it downloads several GB to build the Docker image.

**✅ Check:** a list of `OK` / `WARN` lines.

| Line | What a WARN means |
|---|---|
| Board / model | not a Jetson, or not JetPack 4 |
| Power mode | `nvpmodel` missing |
| Docker + NVIDIA runtime | install `docker.io nvidia-container-runtime` |
| Swap | (it creates 4 GB of swap itself) |
| Build edge-drone image | re-run the script if the download failed |
| Files not in git | expected now: you copy them in the next step |
| Camera | expected now: the webcam comes in Step 21 |
| Flight-controller UART | expected now: fixed in Step 24 |

### Step 19: Copy the models and test video (laptop → Nano)

**Run (laptop, in the repo folder):**
```bash
scp weights/yolov8n.pt weights/fire_smoke.pt <user>@<nano-ip>:~/Edge_Disasted_Detection_Project/weights/
```
```bash
scp data/mixed_test.mp4 data/mixed_test_labels.json <user>@<nano-ip>:~/Edge_Disasted_Detection_Project/data/
```
**✅ Check (Nano):** `ls weights data` lists all four files.

> **How to run anything on the Nano:** use `jetson/run_docker.sh python3 <script>.py`. It runs inside the prepared Docker container and passes any `EDGE_…` settings you put in front of it. The webcam and serial ports are passed in automatically.

---

# Part E: Connect the parts, one at a time

> ⚠️ **Before touching the 40-pin header:** run `sudo poweroff`, wait for the LED to go off, then **unplug the power**.

### Step 20: Power and fan check (Nano)

**Run:**
```bash
jetson/run_docker.sh python3 power_monitor.py
```
**✅ Check:** `power source: sysfs:POM_5V_IN` and `idle: ~1500–2500 mW`. The fan should be spinning.

### Step 21: Connect the Lenovo webcam

**Do:** plug it into any **blue USB 3.0 port**, and **slide the privacy shutter open**.

**Run (Nano):**
```bash
ls /dev/video*
```
**✅ Check:** `/dev/video0`.

### Step 22: Take a test picture (Nano)

**Run:**
```bash
jetson/run_docker.sh python3 -c "import cv2; c=cv2.VideoCapture(0); c.read(); ok,f=c.read(); print(ok, f.shape); cv2.imwrite('data/cam_test.jpg', f)"
```
**✅ Check:** `True (720, 1280, 3)` (or similar). Copy it to the laptop with `scp <user>@<nano-ip>:~/Edge_Disasted_Detection_Project/data/cam_test.jpg .` and open it. It should not be black.

### Step 23: Identify the GPS wires (safety first)

**Do:**
1. Look at the **6-pin GPS plug** on the M8N puck. Many modules print **VCC / GND / TX / RX** (sometimes SDA / SCL too) on the PCB or the cable. **The colours and order differ between sellers, so never guess.**
2. Without labels, use the multimeter. Power the puck from 5 V: **GND–VCC ≈ 5 V**, and **TX ≈ 3.3 V** at idle (measured against GND).
3. Ignore the **4-pin compass plug** completely.

### Step 24: Wire the GPS (pick one option)

**Option A (recommended): USB-serial adapter.** Set the adapter's jumper to 3.3 V if it has one.

| GPS wire | → Adapter pin |
|---|---|
| VCC | 5V |
| GND | GND |
| TX | **RX** |
| RX | **TX** |

Plug the adapter into a Nano USB port. It becomes **`/dev/ttyUSB0`**.

**Option B: the Nano's 40-pin header (UART, `/dev/ttyTHS1`).**

```
   Nano 40-pin header J41 (pin numbers are printed on the board)
        3V3  (1) (2)  5V   ◄── GPS VCC     (or pin 4 if the fan uses pin 2)
             (3) (4)  5V
             (5) (6)  GND  ◄── GPS GND     (or pin 9 / 14 if the fan uses pin 6)
             (7) (8)  TX  ──► GPS RX
        GND  (9) (10) RX  ◄── GPS TX
```

TX always goes to RX (crossed over). ⚠️ The Nano's pins 8 and 10 take **3.3 V only**.

Then free the UART from the Linux console (once):
```bash
sudo systemctl disable --now nvgetty
sudo usermod -aG dialout $USER
```
Log out and SSH back in.

### Step 25: Test the GPS outdoors (Nano)

**Do:** go outside, or put the puck at a window with open sky. The first fix can take **30 s to 3 minutes**.

**Run** (use `/dev/ttyUSB0` for Option A):
```bash
EDGE_GPS=nmea EDGE_GPS_PORT=/dev/ttyTHS1 jetson/run_docker.sh python3 gps_source.py
```
**✅ Check:**
```
[gps] nmea /dev/ttyTHS1 @ 9600 baud (fix comes later if the sky view is poor)
no fix  sats=3 hdop=None sentences=12
...
12.97xxxx, 77.59xxxx  sats=9 hdop=0.9 sentences=240
```

**If it isn't working:**
- `no NMEA data` → TX/RX not crossed, no power, or `nvgetty` still on.
- `sentences` rising but `no fix` → the wiring is fine; it needs a better view of the sky.

### Step 26: Checkpoint

**✅ Check:** the power sensor works, the webcam takes pictures, and the GPS gets a fix. Power off, tidy the cables, and power on again.

---

# Part F: Detection models on the Nano (still with internet)

### Step 27: Maximum performance (Nano)

**Run:**
```bash
sudo nvpmodel -m 0 && sudo jetson_clocks
```

### Step 28: Check the models load on the GPU (Nano)

**Run:**
```bash
EDGE_DEVICE=0 jetson/run_docker.sh python3 check_fire_model.py data/mixed_test.mp4
```
**✅ Check:** `classes: {0: 'fire', 1: 'smoke'}`, plus detection lines.

**If it fails with "unknown module/layer"**, the container's AI library is too old for this fire model. Run:
```bash
sudo docker build --build-arg UPGRADE_ULTRALYTICS=1 -t edge-drone jetson/
```
Then retry. If it still fails: on the **laptop**, run `python export_onnx.py`, copy `weights/fire_smoke.onnx` to the Nano, and add `EDGE_FIRE_WEIGHTS=weights/fire_smoke.onnx` to the commands.

### Step 29: Benchmark (Nano)

**Run:**
```bash
EDGE_DEVICE=0 jetson/run_docker.sh python3 benchmark.py --tag nano_pytorch
```
**✅ Check:** a results table and `saved data/benchmark_nano_pytorch.json`, including energy numbers. This is your project's main result: keep it.

### Step 30: Make the AI fast with TensorRT (Nano)

**Run (it takes several minutes per model):**
```bash
jetson/run_docker.sh python3 export_trt.py
```
```bash
EDGE_DEVICE=0 EDGE_PERSON_WEIGHTS=weights/yolov8n.engine EDGE_FIRE_WEIGHTS=weights/fire_smoke.engine jetson/run_docker.sh python3 benchmark.py --tag nano_trt
```
**✅ Check:** `weights/*.engine` files exist, and `benchmark_nano_trt.json` shows a much faster Stage 2 than Step 29.

---

# Part G: Field Wi-Fi (no router, no internet)

### Step 31: Turn the Nano into a Wi-Fi hotspot (Nano)

**Run:**
```bash
sudo jetson/hotspot.sh --password 'choose-a-long-password'
```
**✅ Check:** `hotspot up: SSID 'DRONE-EDGE' on wlan0, Nano at 10.42.0.1, starts at boot`. **Write the password down.**

> If it says the card has **no AP mode**, use a phone hotspot that both devices join instead. Everything else works the same.

### Step 32: Join from the laptop

**Do:** connect the laptop's Wi-Fi to **DRONE-EDGE**.

**Run (laptop):**
```bash
ssh <user>@10.42.0.1
```
**✅ Check:** you're on the Nano. From now on, the Nano is always **`10.42.0.1`**.

### Step 33: Allow the station through the laptop firewall (once)

**Do:**
- **macOS:** the first time you start `python ground_station/app.py`, click **Allow** on "accept incoming network connections" (or System Settings → Network → Firewall → Options → allow Python).
- **Windows:** on the Defender prompt, tick **Private networks**, then **Allow**. Set the DRONE-EDGE network to **Private**.

### Step 34: Back to normal Wi-Fi later

If you need home internet on the Nano again (for updates), **run** `sudo jetson/hotspot.sh --off`. Turn the hotspot back on with Step 31.

---

# Part H: First full live run

### Step 35: Start the ground station (laptop, on DRONE-EDGE)

**Run:**
```bash
source venv/bin/activate          # Windows: venv\Scripts\Activate.ps1
python ground_station/app.py
```
Then open **http://localhost:5050**. **✅ Check:** the top bar says **WAITING FOR DRONE**.

### Step 36: Start the pipeline (Nano, SSH to 10.42.0.1)

Use `/dev/ttyUSB0` if you wired the GPS with the adapter.

**Run:**
```bash
cd ~/Edge_Disasted_Detection_Project
EDGE_DEVICE=0 EDGE_SOURCE=0 EDGE_GPS=nmea EDGE_GPS_PORT=/dev/ttyTHS1 \
EDGE_PERSON_WEIGHTS=weights/yolov8n.engine EDGE_FIRE_WEIGHTS=weights/fire_smoke.engine \
jetson/run_docker.sh python3 run_pipeline.py
```
**✅ Check (Nano):**
```
[gps] nmea /dev/ttyTHS1 @ 9600 baud …
[link] station: auto (waiting for the ground station beacon on UDP 5005)
[camera] usb 1280x720 @ 30 fps
[link] ground station found at http://10.42.0.xx:5050
```
**✅ Check (dashboard), within about 2 s:**
- **LIVE · `<nano name>`**
- `FIX · N sats` (or `NO FIX` indoors)
- the live camera picture
- the Flight panel with real power and temperatures

You never typed the laptop's IP: the station announced itself and the drone found it.

### Step 37: Indoor fire test

**Do:** play a fire video on a phone or monitor and point the webcam at it.

**✅ Check:**
- the Flight panel shows **ACTIVE** and the camera shows **YOLO ACTIVE**
- a **fire alert** pops up with a beep
- a card appears in the Alerts drawer with the photo
- indoors it says **no GPS fix**; outdoors it has coordinates

Click **Acknowledge**, then **Resolve**.

### Step 38: Link-loss test

**Do:** turn the laptop's Wi-Fi off for 20 s, or walk out of range.

**✅ Check:**
- the dashboard shows **LINK LOST**
- any detection made meanwhile shows up on the **Waiting** card in the Flight panel (alerts held on the drone)
- after reconnecting, the waiting alerts arrive with their pop-ups. **Nothing is lost.**

### Step 39: Stop cleanly

**Do:** press **Ctrl+C** on the Nano.

**✅ Check:** `[stop] stopping, flushing alerts`, then a summary table.

---

# Part I: Start at boot, and mount on the drone

### Step 40: Install the autostart service (Nano)

**Run:**
```bash
sudo jetson/install_service.sh
sudo nano /etc/default/edge-drone
```
In the editor, check `EDGE_GPS_PORT` (`/dev/ttyTHS1` or `/dev/ttyUSB0`) and leave `EDGE_SERVER_URL=auto`. Save with Ctrl+O, Enter, Ctrl+X.

### Step 41: Start it and watch the log (Nano)

**Run:**
```bash
sudo systemctl start edge-drone
journalctl -u edge-drone -f
```
**✅ Check:** the same lines as Step 36. Leave the log with Ctrl+C. To turn autostart off later: `sudo systemctl disable --now edge-drone`.

### Step 42: Reboot test

**Do:** `sudo reboot`. Wait about 1–2 minutes, keeping the laptop on DRONE-EDGE with the station running.

**✅ Check:** the dashboard goes **LIVE** with no keyboard or SSH needed. This is how it runs on the drone.

### Step 43: Power from the drone battery

**Do:** use a **5 V ≥ 4 A UBEC/BEC** from the drone battery, its output wired to a 5.5 × 2.1 mm barrel plug (centre +).

- Measure the output with the multimeter **before** connecting the Nano: it must read **4.9–5.2 V**.
- Keep the **J48** jumper on.

### Step 44: Mount everything

**Do:**
- **Webcam:** pointing **down** (for search), rigid, with the shutter open and the lens clean.
- **GPS puck:** on **top**, flat, with clear sky, at least 10 cm from the Nano, the power wires and the motors (interference).
- **Nano:** keep the fan's air path open, and use foam or soft mounts against vibration.
- **Cables:** strain-relief all of them (zip ties), with no loose wires near the propellers.
- **Wi-Fi antenna:** pointing down or sideways toward the ground station, not covered by carbon or metal.

**✅ Check:** power on the drone; the dashboard shows **LIVE**, `FIX`, and the camera picture.

---

# Part J: Mission day, and after

### Step 45: Mission day checklist

**The day before (with internet)**
- [ ] Map and terrain tiles saved for the flight area (Step 10, Do 5)
- [ ] `git pull` on the laptop **and** the Nano
- [ ] All batteries charged: drone, laptop and the UBEC source
- [ ] Hotspot password written down

**On site, before take-off**
- [ ] Fan spinning, J48 jumper on, webcam shutter open
- [ ] Laptop joined to **DRONE-EDGE**, `python ground_station/app.py` running, dashboard open, 🔔 sound on
- [ ] Top bar shows **LIVE** and **FIX · ≥ 6 sats**
- [ ] Camera picture updating
- [ ] Test: show a fire picture on a phone to the camera → alert + beep
- [ ] **New mission** (top bar, or ⌘K) named e.g. `Site A – 12 Nov`

**During the flight**
- [ ] Watch for **LINK LOST**: alerts wait on the drone and arrive when it's back in range.
- [ ] **Person** alerts show a red banner until acknowledged. **Acknowledge** them when the team responds, **Resolve** when done, and add a **Note** (e.g. "team 2 dispatched").

**After landing**
- [ ] The **Waiting** card in the Flight panel shows **0 alerts** before you power off.

### Step 46: Review the mission

**Do:**
- **Replay** (left rail): play the flight back at 16×, and click alert ticks to jump to each event.
- **Analytics:** check the **compute saved** percentage, power and temperatures. **Table** shows the raw numbers.

### Step 47: Export and back up

**Do:** use **Export** (top bar) or the **Missions** view.

| Export | Open it with |
|---|---|
| CSV | Excel / Google Sheets |
| GeoJSON | QGIS / GIS tools |
| KML | **Google Earth**: coloured placemarks plus the flight track |
| Report | the browser. **Print → Save as PDF** for a mission report with photos. |

**Back up** the folder `ground_station/received/` after important missions. It holds all missions, photos and saved maps.

🎉 **That's the whole system, from parts to a flown and reported mission.**

---

# Troubleshooting

| Symptom | Fix |
|---|---|
| `localhost:5050` shows nothing, or an old note says 5000 and you get "403" | the station isn't running (start it, Step 8). Port **5000** on a Mac belongs to **AirPlay Receiver** (403 AirTunes), which is why the station uses **5050**. Run on any free port with `GS_PORT=<port> python ground_station/app.py`. |
| Nano won't power on from the barrel jack | J48 jumper missing (Step 13) |
| Nano resets when the AI starts | weak power: use 5 V **4 A** with J48 (Step 13), or a stronger UBEC (Step 43) |
| `Could not open source: 0` | webcam not plugged in (`ls /dev/video*`), Step 21 |
| Camera picture is black | the webcam privacy shutter is closed |
| `no NMEA data on /dev/tty…` | TX/RX not crossed, GPS not powered, or `nvgetty` still on (Step 24) |
| GPS stuck at `no fix` | no sky view: go outside and wait up to 3 min |
| Dashboard stuck on **WAITING FOR DRONE** | laptop not on DRONE-EDGE; firewall blocking Python (Step 33); the Nano log lacks `ground station found`. Workaround: `EDGE_SERVER_URL=http://<laptop-ip>:5050` on the Nano. Test from the Nano: `curl http://<laptop-ip>:5050/health`. |
| **Reconnecting…** in the top bar | the station isn't running or the laptop lost Wi-Fi. It recovers by itself once it's back. |
| **LINK LOST** while flying | out of Wi-Fi range or the pipeline stopped. Alerts are buffered and arrive later. |
| Map grey or blank in the field | the area wasn't saved: redo Step 10 Do 5 at home |
| 3D shows "Terrain not cached for this area" | prefetch with `--terrain` (Step 10 Do 5). The map still tilts, just flat. |
| "Map needs WebGL" | the laptop browser has no GPU support: use Chrome or Edge, and update graphics drivers. Alerts, camera, replay and analytics still work. |
| No alert sound | click 🔔 once; check the mute button |
| `Dashboard not built` page | someone deleted `ground_station/static/app/`: run `git checkout ground_station/static/app`, or rebuild it (see the dashboard UI section below) |
| `check_fire_model.py` fails on the Nano | Step 28 fallbacks |
| TensorRT export killed | out of memory: re-run `jetson/setup_nano.sh` (swap) and log out of the desktop |
| Panels show **WARM** / **HOT** | check the fan spins and the airflow isn't blocked (HOT is ≥ 80 °C) |
| `bad link key` (401) | `GS_LINK_KEY` (laptop) and `EDGE_LINK_KEY` (Nano) must match, or leave both unset |

---

# Coding guide

### Where things live

| You want to change… | File |
|---|---|
| Settings and thresholds | `config.py` (environment variables override some; see Reference) |
| How pictures are taken | `frame_source.py` |
| The cheap Stage 1 check | `stage1_gate.py` |
| The AI models, and how often they run | `stage2_detector.py` |
| What becomes an alert (cooldown, person threshold) | `alert_store.py` |
| GPS (sim / M8N NMEA / MAVLink) | `gps_source.py`, `gps_sim.py` |
| What the drone sends to the laptop | `link.py`, `system_stats.py` |
| The main loop | `run_pipeline.py` |
| Station API and database | `ground_station/app.py`, `store.py`, `tiles.py`, `exports.py` |
| **Dashboard UI** (React + TypeScript) | `ground_station/web/src/`. Build output in `ground_station/static/app/` |
| Jetson scripts | `jetson/` |

### Common changes

- **Tune Stage 1 on your footage:** `python test_stage1.py`, then adjust `FIRE_HSV_*`, `FIRE_PIXEL_FRACTION` and `DIFF_FRACTION` in `config.py`.
- **Change how often YOLO runs during a fire:** `EDGE_STAGE2_EVERY_N` (`1` = every frame, `3` = default).
- **Change alert sensitivity:** `CONF_THRESHOLD`, `PERSON_ALERT_CONF`, `ALERT_COOLDOWN_SEC`.
- **Add a new detection type** (e.g. "flood"):
  1. Load its model in `stage2_detector.py`.
  2. Add it to `PRIORITY` in `alert_store.py` and `ground_station/app.py`, and to `TYPES` in `ground_station/exports.py`.
  3. In the UI: add it to `ALERT_TYPES`/`PRIORITY` in `web/src/lib/types.ts`, and to `LETTER` in `web/src/ui/Badge.tsx` and `web/src/features/map/markers.ts`.
  4. Add a colour token in `web/src/styles/tokens.css` (dark and light) that colour-blind users can tell apart from blue, orange and aqua.
  5. Rebuild the UI, and add tests.

### Working on the dashboard UI

You need this only if you change the dashboard. Running the station never needs Node.

- **Install Node 22** (22.12 or newer) from nodejs.org.
- **Install the packages:**
  ```bash
  cd ground_station/web && npm ci
  ```
- **Live development:** with `python ground_station/app.py` running in another terminal:
  ```bash
  npm run dev
  ```
  Then open http://localhost:5173/static/app/.
- **Unit tests and type check:**
  ```bash
  npm test && npm run typecheck
  ```
- **End-to-end tests** (the first time, run `npx playwright install chromium`):
  ```bash
  GS_PYTHON=../../venv/bin/python npm run test:e2e
  ```
  On Windows, `GS_PYTHON` is `..\..\venv\Scripts\python.exe`.
- **Build, check, and commit the build together with your source:**
  ```bash
  npm run build && npm run check:build
  ```
  ```bash
  git add ground_station/web ground_station/static/app
  ```

| UI folder | What's in it |
|---|---|
| `src/lib/` | API client, types, server clock, formatting, geometry, saved preferences |
| `src/store/` | live state, selection, map commands, dialogs |
| `src/features/shell/` | top bar, navigation, ⌘K palette, notifications, person banner |
| `src/features/map/` | MapLibre map: offline style, 3D terrain, drone animation, alert clusters |
| `src/features/live/`, `alerts/`, `replay/`, `analytics/`, `missions/` | the four views |
| `tests/unit/`, `tests/e2e/` | Vitest and Playwright tests |

### How we work

1. `git pull` on `temp-jetson-fixes` or your own `temp-*` branch. **Never push `main`.**
2. Test first, then code. Run `python -m pytest`, and for UI changes also `npm test` and `npm run test:e2e`.
3. Check the dashboard with `demo_drone.py` (Step 8) before trying it on the Nano.
4. Drone-side Python must stay **3.8-compatible** (it runs in the JetPack 4 container).

---

# Reference

### Commands

| Where | Command | What it does |
|---|---|---|
| laptop | `python ground_station/app.py` | ground station + dashboard (http://localhost:5050) |
| laptop | `python ground_station/demo_drone.py --station http://localhost:5050` | simulated drone |
| laptop | `python ground_station/tiles.py prefetch --bbox lat1,lon1,lat2,lon2 --zoom 14-18 --terrain` | save map + 3D terrain for offline use |
| laptop | `python -m pytest` | backend tests |
| laptop | `cd ground_station/web && npm test` | dashboard tests |
| Nano | `jetson/setup_nano.sh` | one-time setup |
| Nano | `jetson/run_docker.sh python3 run_pipeline.py` | the drone pipeline |
| Nano | `jetson/run_docker.sh python3 gps_source.py` | GPS test |
| Nano | `jetson/run_docker.sh python3 power_monitor.py` | power sensor test |
| Nano | `jetson/run_docker.sh python3 benchmark.py --tag NAME` | benchmark (time + energy) |
| Nano | `jetson/run_docker.sh python3 export_trt.py` | build TensorRT engines |
| Nano | `jetson/run_docker.sh python3 forward_now.py` | send buffered alerts now |
| Nano | `sudo jetson/hotspot.sh` / `--off` | field Wi-Fi on / off |
| Nano | `sudo jetson/install_service.sh` | start at boot |
| Nano | `journalctl -u edge-drone -f` | live log |

### Settings (environment variables)

| Variable | Default | Meaning |
|---|---|---|
| `EDGE_SOURCE` | `data/mixed_test.mp4` | `0` = USB webcam, a video path, `csi`, or an MJPEG URL |
| `EDGE_DEVICE` | `cpu` | `0` = Jetson GPU |
| `EDGE_PERSON_WEIGHTS` / `EDGE_FIRE_WEIGHTS` | `weights/*.pt` | `.pt`, `.engine` (TensorRT) or `.onnx` |
| `EDGE_GPS` | `sim` | `nmea` for the M8N, `sim` for the simulated path, `mavlink` for a flight controller |
| `EDGE_GPS_PORT` / `EDGE_GPS_BAUD` | `/dev/ttyTHS1` / auto | GPS serial port |
| `EDGE_SERVER_URL` | `auto` | finds the laptop by itself, or `http://<laptop-ip>:5050` |
| `EDGE_DRONE_ID` / `EDGE_LINK_KEY` | hostname / none | name on the dashboard / shared key |
| `EDGE_MOTION_COMP` / `EDGE_STAGE2_EVERY_N` | `1` / `3` | Stage 1 motion compensation / YOLO frequency while confirmed |
| `GS_HOST` / `GS_PORT` | `0.0.0.0` / `5050` | station address (`127.0.0.1` = this laptop only) |
| `GS_DATA_DIR` / `GS_LINK_KEY` | `ground_station/received` / none | station data folder / key the drone must send |

### Ports

| Port | Used for |
|---|---|
| TCP 5050 | drone → laptop (alerts, status, pictures), and the dashboard |
| UDP 5005 | the laptop announces itself to the drone |

### Where data is stored

| Where | What |
|---|---|
| Nano `data/alerts.db`, `data/snapshots/` | alerts waiting to be sent, and their photos |
| Nano `data/benchmark_*.json` | benchmark results |
| Laptop `ground_station/received/station.db` | all missions, alerts, notes, the flight track and telemetry history |
| Laptop `ground_station/received/snaps/` | alert photos |
| Laptop `ground_station/received/tiles/`, `terrain/` | saved map and 3D terrain |
