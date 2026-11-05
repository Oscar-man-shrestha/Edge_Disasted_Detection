"""Live link from the drone to the ground station, in one background thread.

    state = LinkState()                     # the frame loop feeds this (cheap, no I/O)
    link = DroneLink(state, gps, StationFinder(fixed_url=None)).start()
    ...
    link.stop()                             # final alert flush, max ~5 s

Channels, each on its own timer with backoff (1/2/4/8 s) when the station is unreachable:
  telemetry  every TELEMETRY_INTERVAL_SEC   POST /api/telemetry  (latest wins, never queued)
  preview    every PREVIEW_INTERVAL_SEC     POST /api/preview    (latest wins, never queued)
  alerts     every ALERT_FORWARD_INTERVAL_SEC  POST /alert       (store-and-forward, never lost)
Python 3.8 compatible (runs in the JetPack 4 container).
"""
import json
import socket
import threading
import time
from collections import deque

import cv2

import config
from alert_store import AlertStore

SERVICE = "edge-gs"
STATION_TIMEOUT_S = 10.0
DEFAULT_STATION_PORT = 5050      # station default (5000 is taken by macOS AirPlay)
ACTIVE_WINDOW_S = 3.0
BOX_COLORS = {"person": (255, 150, 40), "fire": (0, 0, 255), "smoke": (180, 180, 180)}
BACKOFF_MAX_S = 8.0


# --------------------------------------------------------------------------- state
class LinkState:
    """Shared between the frame loop (writer) and the link thread (reader)."""

    def __init__(self):
        self._lock = threading.Lock()
        self.started = time.time()
        self.last_frame = None
        self.last_frame_time = None
        self.t = None
        self.frames = 0
        self.triggers = 0
        self.stage2_runs = 0
        self.stage2_skipped = 0
        self.stage1_ms = None
        self.stage2_ms = None
        self.last_stage2_time = None
        self.dets = []
        self.dets_time = None
        self._times = deque(maxlen=10)

    def frame(self, frame_bgr, gate_result, ran_stage2, stage2_ms=None, t=None, skipped=None):
        now = time.time()
        with self._lock:
            self.last_frame = frame_bgr               # reference only; encoded in the link thread
            self.last_frame_time = now
            self.t = t
            self.frames += 1
            self._times.append(now)
            if gate_result:
                self.stage1_ms = gate_result.get("ms")
                if gate_result.get("trigger"):
                    self.triggers += 1
            if ran_stage2:
                self.stage2_runs += 1
                self.last_stage2_time = now
                if stage2_ms is not None:
                    self.stage2_ms = stage2_ms
            if skipped is not None:
                self.stage2_skipped = skipped

    def detections(self, dets, t):
        with self._lock:
            self.dets = list(dets)
            self.dets_time = t

    def preview_source(self):
        """(frame, recent detections, stage2_active) for the preview channel."""
        now = time.time()
        with self._lock:
            recent = self.dets if self.dets_time and now - self.dets_time < ACTIVE_WINDOW_S else []
            active = bool(self.last_stage2_time and now - self.last_stage2_time < ACTIVE_WINDOW_S)
            return self.last_frame, list(recent), active, self.last_frame_time

    def snapshot(self):
        """The telemetry 'pipeline' block."""
        now = time.time()
        with self._lock:
            if self.last_frame_time is None or now - self.last_frame_time > ACTIVE_WINDOW_S:
                st = "idle"
            elif self.last_stage2_time and now - self.last_stage2_time < ACTIVE_WINDOW_S:
                st = "active"
            else:
                st = "scanning"
            fps = None
            if len(self._times) >= 2 and self._times[-1] > self._times[0]:
                fps = round((len(self._times) - 1) / (self._times[-1] - self._times[0]), 2)
            last = None
            if self.dets:
                best = max(self.dets, key=lambda d: d["conf"])
                last = {"type": best["type"], "conf": round(best["conf"], 3), "t": self.dets_time}
            return {"state": st, "fps": fps, "frames": self.frames,
                    "stage1_ms": None if self.stage1_ms is None else round(self.stage1_ms, 1),
                    "stage2_ms": None if self.stage2_ms is None else round(self.stage2_ms, 1),
                    "stage2_runs": self.stage2_runs, "stage2_skipped": self.stage2_skipped,
                    "triggers": self.triggers, "last_detection": last}


# --------------------------------------------------------------------------- discovery
class StationFinder:
    """Finds the ground station from its UDP beacon, or uses a fixed URL."""

    def __init__(self, port=None, fixed_url=None):
        self.port = port or config.DISCOVERY_PORT
        self.fixed = None
        if fixed_url and fixed_url != "auto":
            u = fixed_url.rstrip("/")
            if u.endswith("/alert"):
                u = u[:-len("/alert")]
            self.fixed = u
        self._url = None
        self._seen = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._sock = None

    def _on_beacon(self, ip, msg, now=None):
        if not isinstance(msg, dict) or msg.get("service") != SERVICE:
            return
        try:
            url = "http://%s:%d" % (ip, int(msg.get("port", DEFAULT_STATION_PORT)))
        except (TypeError, ValueError):
            return
        now = time.time() if now is None else now
        with self._lock:
            current_alive = self._seen is not None and now - self._seen < STATION_TIMEOUT_S
            if self._url == url:
                self._seen = now
            elif not current_alive:              # switch only when the old one went quiet
                if self._url != url:
                    print("[link] ground station found at %s" % url)
                self._url, self._seen = url, now

    def url(self, now=None):
        if self.fixed:
            return self.fixed
        now = time.time() if now is None else now
        with self._lock:
            if self._seen is None or now - self._seen > STATION_TIMEOUT_S:
                return None
            return self._url

    def start(self):
        if self.fixed:
            return self
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT"):
            try:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except OSError:
                pass
        s.bind(("", self.port))
        s.settimeout(0.5)
        self._sock = s
        threading.Thread(target=self._listen, daemon=True).start()
        return self

    def _listen(self):
        while not self._stop.is_set():
            try:
                data, (ip, _) = self._sock.recvfrom(2048)
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                self._on_beacon(ip, json.loads(data.decode("utf-8", "ignore")))
            except ValueError:
                continue

    def stop(self):
        self._stop.set()
        if self._sock:
            self._sock.close()


# --------------------------------------------------------------------------- preview
def build_preview(frame, dets, width, quality):
    h, w = frame.shape[:2]
    scale = float(width) / w
    small = cv2.resize(frame, (width, int(round(h * scale))), interpolation=cv2.INTER_AREA)
    for d in dets:
        x1, y1, x2, y2 = [int(round(v * scale)) for v in d["box"]]
        color = BOX_COLORS.get(d["type"], (0, 255, 255))
        cv2.rectangle(small, (x1, y1), (x2, y2), color, 2)
        label = "%s %.2f" % (d["type"], d["conf"])
        cv2.putText(small, label, (x1, max(12, y1 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                    color, 1, cv2.LINE_AA)
    ok, buf = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, int(quality)])
    return buf.tobytes() if ok else b""


# --------------------------------------------------------------------------- link
class _Channel:
    def __init__(self, name, interval):
        self.name = name
        self.interval = interval
        self.next_due = 0.0
        self.backoff = 0.0
        self.last_log = 0.0

    def ok(self, now):
        self.backoff = 0.0
        self.next_due = now + self.interval()

    def fail(self, now, err):
        self.backoff = min(BACKOFF_MAX_S, self.backoff * 2 if self.backoff else 1.0)
        self.next_due = now + max(self.interval(), self.backoff)
        if now - self.last_log > 10:
            print("[link] %s: %s (retry in %.0f s)" % (self.name, err, self.backoff))
            self.last_log = now


class DroneLink:
    def __init__(self, state, gps, finder, stats=None, store_factory=AlertStore):
        self.state = state
        self.gps = gps
        self.finder = finder
        self.stats = stats
        self.store_factory = store_factory
        self.seq = 0
        self.alerts_sent = 0
        self._counts = {"buffered": 0, "sent": 0}
        self._stop = threading.Event()
        self._thread = None
        self._channels = [
            _Channel("telemetry", lambda: config.TELEMETRY_INTERVAL_SEC),
            _Channel("preview", lambda: config.PREVIEW_INTERVAL_SEC),
            _Channel("alerts", lambda: config.ALERT_FORWARD_INTERVAL_SEC),
        ]

    # ---- helpers
    @staticmethod
    def _headers():
        h = {"X-Drone-Id": config.DRONE_ID}
        if config.LINK_KEY:
            h["X-Link-Key"] = config.LINK_KEY
        return h

    def _gps_status(self):
        try:
            t = self.state.t if self.state.t is not None else time.time() - self.state.started
            try:
                return self.gps.status(t)
            except TypeError:
                return self.gps.status()
        except Exception as e:                    # GPS trouble must not kill the link
            return {"mode": "error", "fix": False, "error": str(e)[:80]}

    def telemetry(self):
        self.seq += 1
        return {"drone_id": config.DRONE_ID, "seq": self.seq, "time": time.time(),
                "uptime_s": round(time.time() - self.state.started, 1),
                "gps": self._gps_status(), "pipeline": self.state.snapshot(),
                "system": self.stats.read() if self.stats else None,
                "link": {"alerts_buffered": self._counts["buffered"],
                         "alerts_sent": self._counts["sent"]}}

    # ---- channel bodies; raise on failure
    def _send_telemetry(self, requests, url, store):
        self._counts = store.counts()
        r = requests.post(url + "/api/telemetry", json=self.telemetry(), headers=self._headers(),
                          timeout=(config.FORWARD_CONNECT_TIMEOUT, 2))
        if r.status_code != 200:
            raise RuntimeError("HTTP %d" % r.status_code)

    def _send_preview(self, requests, url, store):
        frame, dets, active, frame_time = self.state.preview_source()
        if frame is None:
            return
        jpg = build_preview(frame, dets, config.PREVIEW_WIDTH, config.PREVIEW_QUALITY)
        h = self._headers()
        h.update({"Content-Type": "image/jpeg", "X-Stage2-Active": "1" if active else "0",
                  "X-Frame-Time": "%.3f" % (frame_time or time.time())})
        r = requests.post(url + "/api/preview", data=jpg, headers=h,
                          timeout=(config.FORWARD_CONNECT_TIMEOUT, 3))
        if r.status_code != 200:
            raise RuntimeError("HTTP %d" % r.status_code)

    def _send_alerts(self, requests, url, store):
        sent, left = store.forward_pending(url, self._headers())
        self.alerts_sent += sent
        self._counts = store.counts()
        if left:
            raise RuntimeError("%d alert(s) still buffered" % left)

    # ---- thread
    def _run(self):
        import requests
        store = self.store_factory()             # SQLite connection owned by this thread
        bodies = {"telemetry": self._send_telemetry, "preview": self._send_preview,
                  "alerts": self._send_alerts}
        while not self._stop.is_set():
            now = time.time()
            url = self.finder.url()
            if url is None:                       # no station yet: wait for its beacon
                self._stop.wait(0.2)
                continue
            for ch in self._channels:
                if now < ch.next_due or self._stop.is_set():
                    continue
                try:
                    bodies[ch.name](requests, url, store)
                    ch.ok(time.time())
                except Exception as e:
                    ch.fail(time.time(), e.__class__.__name__ if not str(e) else str(e)[:120])
            due = min(ch.next_due for ch in self._channels)
            self._stop.wait(max(0.02, min(0.5, due - time.time())))

    def start(self):
        if hasattr(self.finder, "start") and not getattr(self.finder, "_sock", None):
            self.finder.start()
        self._thread = threading.Thread(target=self._run, name="drone-link", daemon=True)
        self._thread.start()
        return self

    def status(self):
        return {"station": self.finder.url(), "alerts_sent": self.alerts_sent}

    def stop(self, flush_timeout=5.0):
        """Stop the thread, then try once more to deliver buffered alerts (bounded time)."""
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)
        url = self.finder.url()
        if url:
            def flush():
                try:
                    s, _ = self.store_factory().forward_pending(url, self._headers())
                    self.alerts_sent += s
                except Exception:
                    pass
            t = threading.Thread(target=flush, daemon=True)
            t.start()
            t.join(timeout=flush_timeout)
        if hasattr(self.finder, "stop"):
            self.finder.stop()
