"""Ground station: receives the drone's alerts, telemetry and previews; serves the dashboard.

    python ground_station/app.py          # http://localhost:5050, beacon on UDP 5005

Environment: GS_HOST (default 0.0.0.0), GS_PORT (5050), GS_DATA_DIR (ground_station/received),
GS_LINK_KEY (shared key the drone must send), GS_BEACON_TARGETS, GS_BEACON_PORT.
"""
import json
import math
import os
import re
import shutil
import socket
import threading
import time

from flask import Flask, abort, jsonify, render_template, request, send_from_directory

import exports
from discovery import DEFAULT_BEACON_PORT, Beacon
from events import EventBus
from store import Store
import tiles as tiles_mod
from tiles import tiles_blueprint

BASE = os.path.dirname(os.path.abspath(__file__))
PRIORITY = {"person": 1, "fire": 2, "smoke": 3}
# Not 5000: on macOS the AirPlay Receiver (Control Center) listens there and answers 403.
DEFAULT_PORT = 5050
LINK_LOST_SEC = 3.0
PREVIEW_MAX_BYTES = 500 * 1024
DRONE_ROUTES = ("/alert", "/api/telemetry", "/api/preview", "/api/clip")
CLIP_MAX_FRAMES = 120
TELEMETRY_BLOCKS = ("gps", "pipeline", "system", "link")
SNAP_NAME = re.compile(r"^\d+_[a-z]+\.jpg$")
GPS_NUMBERS = ("lat", "lon", "alt_m", "sats", "hdop", "speed_mps", "course_deg", "age_s")


def _finite_or_none(v):
    return v is None or (isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v))


def gps_problem(gps):
    """Why a telemetry gps block is unacceptable, or None. Values are rendered into the
    dashboard and stored in the track, so they must be plain finite numbers."""
    if gps is None:
        return None
    for k in GPS_NUMBERS:
        if not _finite_or_none(gps.get(k)):
            return "gps.%s must be a finite number or null" % k
    if gps.get("fix") not in (None, True, False):
        return "gps.fix must be true, false or null"
    return None


def link_state(live, now):
    """'never' before the first telemetry, 'live' if the last one is < 3 s old, else 'lost'.
    Uses the station's receive time, so drone/laptop clock differences do not matter."""
    t = live.get("received_at")
    if t is None:
        return {"state": "never", "age_s": None}
    age = max(0.0, now - t)
    return {"state": "live" if age < LINK_LOST_SEC else "lost", "age_s": round(age, 1)}


def _opt_float(v):
    if v is None or str(v).strip().lower() in ("", "none", "nan", "null"):
        return None
    return float(v)


def _sorted(alerts):
    return sorted(alerts, key=lambda a: (PRIORITY.get(a["type"], 9), -a["id"]))


def create_app(data_dir=None, link_key="", watcher=True, tile_fetch=None, ui_dir=None,
               terrain_fetch=None):
    # absolute: Flask resolves relative paths against the app folder, not the cwd
    data_dir = os.path.abspath(data_dir or os.path.join(BASE, "received"))
    snap_dir = os.path.join(data_dir, "snaps")
    os.makedirs(snap_dir, exist_ok=True)

    app = Flask(__name__, static_folder=os.path.join(BASE, "static"),
                template_folder=os.path.join(BASE, "templates"))
    store = Store(os.path.join(data_dir, "station.db"))
    store.current_mission()                       # spec: a mission is open from startup
    bus = EventBus()
    live = {"telemetry": None, "received_at": None, "preview_jpeg": None,
            "preview_t": None, "preview_stage2": False, "preview_received_at": None}
    app.config.update(STORE=store, BUS=bus, LIVE=live, DATA_DIR=data_dir, SNAP_DIR=snap_dir)
    app.register_blueprint(tiles_blueprint(os.path.join(data_dir, "tiles"), fetch=tile_fetch))
    app.register_blueprint(tiles_blueprint(os.path.join(data_dir, "terrain"),
                                           fetch=terrain_fetch or tiles_mod.terrain_fetch,
                                           name="terrain", url_prefix="/terrain",
                                           max_zoom=tiles_mod.MAX_ZOOM_TERRAIN))

    # ------------------------------------------------------------ drone auth
    @app.before_request
    def _check_key():
        if link_key and request.path in DRONE_ROUTES and request.method == "POST":
            if request.headers.get("X-Link-Key", "") != link_key:
                return jsonify(error="bad link key"), 401

    # ------------------------------------------------------------ from the drone
    @app.route("/api/telemetry", methods=["POST"])
    def telemetry():
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify(error="expected a JSON object"), 400
        for k in TELEMETRY_BLOCKS:
            if body.get(k) is not None and not isinstance(body[k], dict):
                return jsonify(error="%s must be an object" % k), 400
        problem = gps_problem(body.get("gps"))
        if problem:
            return jsonify(error=problem), 400
        body.setdefault("drone_id", request.headers.get("X-Drone-Id"))
        live["telemetry"] = body
        live["received_at"] = time.time()
        gps = body.get("gps") or {}
        if gps.get("fix") is True and isinstance(gps.get("lat"), (int, float)) \
                and isinstance(gps.get("lon"), (int, float)):
            store.add_track_point(body.get("drone_id") or "drone", live["received_at"],
                                  gps["lat"], gps["lon"], gps.get("alt_m"))
        store.add_telemetry_sample(body.get("drone_id") or "drone", live["received_at"], body)
        bus.publish("telemetry", {"telemetry": body})
        return jsonify(ok=True)

    @app.route("/api/preview", methods=["POST"])
    def preview():
        data = request.get_data(cache=False)
        if len(data) > PREVIEW_MAX_BYTES:
            return jsonify(error="preview too large"), 413
        if not data.startswith(b"\xff\xd8"):
            return jsonify(error="not a JPEG"), 400
        try:
            frame_t = float(request.headers.get("X-Frame-Time", "nan"))
        except ValueError:
            frame_t = float("nan")
        now = time.time()
        live.update(preview_jpeg=data, preview_received_at=now,
                    preview_t=None if frame_t != frame_t else frame_t,
                    preview_stage2=request.headers.get("X-Stage2-Active") == "1")
        bus.publish("preview", {"t": now, "stage2": live["preview_stage2"]})
        return jsonify(ok=True)

    @app.route("/alert", methods=["POST"])
    def receive_alert():
        typ = request.form.get("type", "")
        if typ not in PRIORITY:
            return jsonify(error="bad type"), 400
        try:
            fields = {
                "drone_id": request.form.get("drone_id") or request.headers.get("X-Drone-Id"),
                "drone_alert_id": request.form.get("alert_id"),
                "type": typ,
                "conf": float(request.form["conf"]),
                "lat": _opt_float(request.form.get("lat")),
                "lon": _opt_float(request.form.get("lon")),
                "video_time": float(request.form.get("video_time") or 0),
                "wall_time": request.form.get("wall_time", "")[:40],
            }
        except (KeyError, ValueError):
            return jsonify(error="bad fields"), 400
        alert, created = store.add_alert(fields)
        if not created:
            return jsonify(ok=True, duplicate=True)
        f = request.files.get("snapshot")
        if f:
            name = "%d_%s.jpg" % (alert["id"], typ)
            f.save(os.path.join(snap_dir, name))
            store.set_snapshot(alert["id"], name)
            alert["snapshot"] = name
        where = "no GPS fix" if alert["lat"] is None else "%.6f,%.6f" % (alert["lat"], alert["lon"])
        print("[station] alert #%d %s %.2f @ %s" % (alert["id"], typ, alert["conf"], where))
        bus.publish("alert", {"alert": alert})
        return jsonify(ok=True)

    @app.route("/api/clip", methods=["POST"])
    def receive_clip():
        """Short alert clip from the drone: JPEG frames 000.jpg.. for an alert it already sent."""
        alert = store.find_alert(request.form.get("alert_id"), request.form.get("wall_time"))
        if alert is None:
            return jsonify(error="unknown alert"), 404
        frames = request.files.getlist("frames")
        if not 0 < len(frames) <= CLIP_MAX_FRAMES:
            return jsonify(error="1..%d frames" % CLIP_MAX_FRAMES), 400
        try:
            fps = min(30.0, max(0.2, float(request.form.get("fps") or 2.0)))
        except ValueError:
            fps = 2.0
        path = os.path.join(snap_dir, "clips", str(alert["id"]))
        shutil.rmtree(path, ignore_errors=True)       # a resend replaces the old clip
        os.makedirs(path)
        for i, f in enumerate(frames):
            f.save(os.path.join(path, "%03d.jpg" % i))
        alert = store.set_clip(alert["id"], len(frames), fps)
        print("[station] clip for alert #%d: %d frames" % (alert["id"], len(frames)))
        bus.publish("alert_update", {"alert": alert})
        return jsonify(ok=True)

    @app.route("/clip/<int:aid>/<int:i>.jpg")
    def clip_frame(aid, i):
        path = os.path.join(snap_dir, "clips", str(aid))
        name = "%03d.jpg" % i
        if not os.path.isfile(os.path.join(path, name)):
            abort(404)
        resp = send_from_directory(path, name, mimetype="image/jpeg")
        resp.headers["Cache-Control"] = "max-age=3600"
        return resp

    # ------------------------------------------------------------ for the browser
    def _preview_meta():
        if live["preview_jpeg"] is None:
            return None
        return {"t": live["preview_received_at"], "frame_t": live["preview_t"],
                "stage2": live["preview_stage2"]}

    @app.route("/api/state")
    def state():
        m = store.current_mission()
        return jsonify(server_time=time.time(), mission=m, missions=store.missions(),
                       link=link_state(live, time.time()), telemetry=live["telemetry"],
                       preview=_preview_meta(), alerts=_sorted(store.alerts(m["id"])),
                       track=store.track(m["id"]))

    @app.route("/api/stream")
    def stream():
        q = bus.subscribe()

        def gen():
            from events import format_sse
            yield format_sse("hello", {"server_time": time.time()})
            for chunk in bus.stream(q):
                yield chunk
        return app.response_class(gen(), mimetype="text/event-stream",
                                  headers={"Cache-Control": "no-cache",
                                           "X-Accel-Buffering": "no"})

    @app.route("/api/preview.jpg")
    def preview_jpg():
        if live["preview_jpeg"] is None:
            abort(404)
        resp = app.response_class(live["preview_jpeg"], mimetype="image/jpeg")
        resp.headers["Cache-Control"] = "no-store"
        return resp

    def _json_object():
        """Request body as a dict; {} when empty; None when it is not a JSON object."""
        if not request.get_data(cache=True).strip():
            return {}
        body = request.get_json(silent=True)
        return body if isinstance(body, dict) else None

    def _mission_summary(m):
        alerts, track = store.alerts(m["id"]), store.track(m["id"])
        counts = {t: 0 for t in PRIORITY}
        for a in alerts:
            counts[a["type"]] = counts.get(a["type"], 0) + 1
        m = dict(m)
        m["alert_counts"] = counts
        m["distance_m"] = sum(exports._dist_m(a, b) for a, b in zip(track, track[1:]))
        return m

    @app.route("/api/alerts/<int:aid>", methods=["POST"])
    def update_alert(aid):
        body = _json_object()
        if body is None:
            return jsonify(error="expected a JSON object"), 400
        note = body.get("note")
        if note is not None and not isinstance(note, str):
            return jsonify(error="note must be text"), 400
        try:
            alert = store.update_alert(aid, status=body.get("status"), note=note)
        except ValueError:
            return jsonify(error="status must be new, acknowledged or resolved"), 400
        if alert is None:
            return jsonify(error="no such alert"), 404
        bus.publish("alert_update", {"alert": alert})
        return jsonify(ok=True, alert=alert)

    @app.route("/api/missions", methods=["GET", "POST"])
    def missions():
        if request.method == "GET":
            return jsonify([_mission_summary(m) for m in store.missions()])
        body = _json_object()
        if body is None:
            return jsonify(error="expected a JSON object"), 400
        name = body.get("name") if isinstance(body.get("name"), str) else None
        m = store.new_mission(name.strip()[:80] if name and name.strip() else None)
        bus.publish("mission", {"mission": m})
        return jsonify(ok=True, mission=m)

    EXPORT_MIME = {"csv": "text/csv", "geojson": "application/geo+json",
                   "kml": "application/vnd.google-earth.kml+xml"}

    @app.route("/api/missions/<int:mid>/timeline")
    def timeline(mid):
        m = store.mission(mid)
        if m is None:
            abort(404)
        return jsonify(mission=m, server_time=time.time(), track=store.track(mid),
                       telemetry=store.telemetry_log(mid), alerts=_sorted(store.alerts(mid)))

    @app.route("/api/missions/<int:mid>/export.<fmt>")
    def export(mid, fmt):
        m = store.mission(mid)
        if m is None or fmt not in EXPORT_MIME:
            abort(404)
        alerts, track = _sorted(store.alerts(mid)), store.track(mid)
        if fmt == "csv":
            body = exports.to_csv(alerts)
        elif fmt == "geojson":
            body = json.dumps(exports.to_geojson(alerts, track), indent=1)
        else:
            body = exports.to_kml(m, alerts, track)
        resp = app.response_class(body, mimetype=EXPORT_MIME[fmt])
        resp.headers["Content-Disposition"] = 'attachment; filename="mission-%d.%s"' % (mid, fmt)
        return resp

    @app.route("/report/<int:mid>")
    def report(mid):
        m = store.mission(mid)
        if m is None:
            abort(404)
        alerts, track = _sorted(store.alerts(mid)), store.track(mid)
        return render_template("report.html", mission=m, alerts=alerts,
                               ctx=exports.report_context(m, alerts, track),
                               generated=time.strftime("%Y-%m-%d %H:%M"))

    @app.route("/snap/<path:name>")
    def snap(name):
        if not SNAP_NAME.match(name):             # only "<id>_<type>.jpg", never the database
            abort(404)
        for d in (snap_dir, data_dir):            # v1 snapshots live directly in data_dir
            if os.path.isfile(os.path.join(d, name)):
                return send_from_directory(d, name)
        abort(404)

    @app.route("/alerts.json")
    def alerts_json():
        return jsonify(_sorted(store.alerts()))

    @app.route("/health")
    def health():
        return jsonify(ok=True, server_time=time.time())

    ui_root = ui_dir or os.path.join(BASE, "static", "app")

    @app.route("/")
    def index():
        page = os.path.join(ui_root, "index.html")
        if not os.path.isfile(page):
            return app.response_class(
                "Dashboard not built. Run: cd ground_station/web && npm ci && npm run build\n",
                status=503, mimetype="text/plain")
        resp = send_from_directory(ui_root, "index.html")
        resp.headers["Cache-Control"] = "no-cache"
        return resp

    # ------------------------------------------------------------ link watcher
    if watcher:
        def watch():
            last = None
            while True:
                st = link_state(live, time.time())
                if st["state"] != last:
                    bus.publish("link", st)
                    last = st["state"]
                time.sleep(1.0)
        threading.Thread(target=watch, daemon=True).start()

    return app





def _default_host():
    """'::' (IPv6 + IPv4) when available: browsers often try localhost as ::1 first,
    and an IPv4-only server then looks offline. Falls back to 0.0.0.0."""
    try:
        s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        s.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        s.close()
        return "::"
    except (OSError, AttributeError):
        return "0.0.0.0"


def main():
    host = os.environ.get("GS_HOST") or _default_host()
    port = int(os.environ.get("GS_PORT", str(DEFAULT_PORT)))
    data_dir = os.environ.get("GS_DATA_DIR") or None
    # 10.42.0.x = the Nano's hotspot, 192.168.55.x = the Nano's USB cable link
    targets = os.environ.get("GS_BEACON_TARGETS",
                             "255.255.255.255,10.42.0.255,192.168.55.255").split(",")
    beacon_port = int(os.environ.get("GS_BEACON_PORT", str(DEFAULT_BEACON_PORT)))
    key = os.environ.get("GS_LINK_KEY", "").strip()
    if "GS_LINK_KEY" not in os.environ:           # unset: same .link_key file the drone reads
                                                  # (set but empty = key explicitly off)
        try:
            with open(os.path.join(os.path.dirname(BASE), ".link_key")) as f:
                key = f.readline().strip()
        except OSError:
            key = ""
    app = create_app(data_dir, link_key=key)
    Beacon(port, targets, beacon_port=beacon_port).start()
    print("Ground station on http://localhost:%d  (host %s, %s)" % (port, socket.gethostname(), host))
    print("Beacon: UDP %d -> %s" % (beacon_port, ", ".join(targets)))
    print("Link key: %s" % ("ON (drones must send the same key)" if key else "off (any drone accepted)"))
    app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
