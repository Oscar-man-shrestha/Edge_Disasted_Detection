"""Ground station: receives the drone's alerts, telemetry and previews; serves the dashboard.

    python ground_station/app.py          # http://localhost:5000, beacon on UDP 5005

Environment: GS_HOST (default 0.0.0.0), GS_PORT (5000), GS_DATA_DIR (ground_station/received),
GS_LINK_KEY (shared key the drone must send), GS_BEACON_TARGETS, GS_BEACON_PORT.
"""
import json
import os
import socket
import threading
import time

from flask import Flask, abort, jsonify, render_template, request, send_from_directory

import exports
from discovery import DEFAULT_BEACON_PORT, Beacon
from events import EventBus
from store import Store
from tiles import tiles_blueprint

BASE = os.path.dirname(os.path.abspath(__file__))
PRIORITY = {"person": 1, "fire": 2, "smoke": 3}
LINK_LOST_SEC = 3.0
PREVIEW_MAX_BYTES = 500 * 1024
DRONE_ROUTES = ("/alert", "/api/telemetry", "/api/preview")
TELEMETRY_BLOCKS = ("gps", "pipeline", "system", "link")


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


def create_app(data_dir=None, link_key="", watcher=True, tile_fetch=None):
    data_dir = data_dir or os.path.join(BASE, "received")
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
        body.setdefault("drone_id", request.headers.get("X-Drone-Id"))
        live["telemetry"] = body
        live["received_at"] = time.time()
        gps = body.get("gps") or {}
        if gps.get("fix") is True and isinstance(gps.get("lat"), (int, float)) \
                and isinstance(gps.get("lon"), (int, float)):
            store.add_track_point(body.get("drone_id") or "drone", live["received_at"],
                                  gps["lat"], gps["lon"], gps.get("alt_m"))
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

    @app.route("/api/alerts/<int:aid>", methods=["POST"])
    def update_alert(aid):
        body = request.get_json(silent=True) or {}
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
            return jsonify(store.missions())
        body = request.get_json(silent=True) or {}
        name = body.get("name") if isinstance(body.get("name"), str) else None
        m = store.new_mission(name.strip()[:80] if name and name.strip() else None)
        bus.publish("mission", {"mission": m})
        return jsonify(ok=True, mission=m)

    EXPORT_MIME = {"csv": "text/csv", "geojson": "application/geo+json",
                   "kml": "application/vnd.google-earth.kml+xml"}

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
        if os.path.basename(name) != name or name.startswith("."):
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

    @app.route("/")
    def index():
        return render_template("index.html") if os.path.isfile(
            os.path.join(BASE, "templates", "index.html")) else LEGACY_PAGE

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


LEGACY_PAGE = """  # v1 page, replaced by templates/index.html in Task 9
<!doctype html>
<html><head><meta charset="utf-8"><title>Ground Station</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  body { font-family: system-ui, sans-serif; margin: 0; background: #111; color: #eee; }
  h1 { margin: 0; padding: 12px 16px; font-size: 18px; background: #1b1b1b; }
  #map { height: 340px; background: #181818; }
  #map svg text { fill: #888; font-size: 11px; }
  .note { padding: 4px 16px; font-size: 12px; opacity: .6; }
  table { width: 100%; border-collapse: collapse; }
  th, td { padding: 8px 12px; border-bottom: 1px solid #2a2a2a; text-align: left; font-size: 14px; }
  img { height: 48px; border-radius: 4px; }
  .badge { padding: 2px 8px; border-radius: 10px; font-weight: 600; color: #000; }
  .person { background: #4da3ff; } .fire { background: #ff6b3d; } .smoke { background: #b0b0b0; }
</style></head>
<body>
<h1>Drone Ground Station <span id="count" style="opacity:.6"></span></h1>
<div id="map"></div><div class="note" id="mapnote"></div>
<table><thead><tr><th>#</th><th>Time</th><th>Type</th><th>Conf</th><th>Lat</th><th>Lon</th><th>Snapshot</th></tr></thead>
<tbody id="rows"></tbody></table>
<script>
const colors = {person: '#4da3ff', fire: '#ff6b3d', smoke: '#b0b0b0'};
const online = typeof L !== 'undefined';
let map, layer, fitted = false;
if (online) {
  map = L.map('map').setView([12.9715, 77.5905], 17);
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom: 19, attribution: '&copy; OpenStreetMap'}).addTo(map);
  layer = L.layerGroup().addTo(map);
} else {
  document.getElementById('mapnote').textContent = 'Offline: map tiles unavailable, showing positions on a plain grid.';
}

function esc(s) { const d = document.createElement('div'); d.textContent = s == null ? '' : s; return d.innerHTML; }
function fmt(v) { return v == null ? 'no fix' : v.toFixed(6); }

// Offline fallback: plot lat/lon on a plain SVG grid (equirectangular, fine for a few km).
function drawOffline(pts) {
  const el = document.getElementById('map'), W = el.clientWidth, H = el.clientHeight, pad = 30;
  if (!pts.length) { el.innerHTML = ''; return; }
  let la0 = Math.min(...pts.map(p => p.lat)), la1 = Math.max(...pts.map(p => p.lat));
  let lo0 = Math.min(...pts.map(p => p.lon)), lo1 = Math.max(...pts.map(p => p.lon));
  const span = Math.max(la1 - la0, (lo1 - lo0) * Math.cos(la0 * Math.PI / 180), 1e-4);
  const s = Math.min(W, H) - 2 * pad;
  const x = lon => pad + (lon - lo0) * Math.cos(la0 * Math.PI / 180) / span * s;
  const y = lat => H - pad - (lat - la0) / span * s;
  let svg = '<svg width="' + W + '" height="' + H + '">';
  svg += '<text x="8" y="16">' + la1.toFixed(5) + ', ' + lo0.toFixed(5) + '</text>';
  svg += '<text x="8" y="' + (H - 8) + '">' + la0.toFixed(5) + ', ' + lo0.toFixed(5) + '  (' + Math.round(span * 111320) + ' m across)</text>';
  for (const p of pts) svg += '<circle cx="' + x(p.lon) + '" cy="' + y(p.lat) + '" r="8" fill="' + colors[p.type] + '" fill-opacity=".75"><title>' + esc(p.type) + ' ' + p.conf.toFixed(2) + '</title></circle>';
  el.innerHTML = svg + '</svg>';
}

async function refresh() {
  let data;
  try { data = await (await fetch('/alerts.json')).json(); } catch (e) { return; }
  document.getElementById('count').textContent = '(' + data.length + ' alerts)';
  const located = data.filter(a => a.lat != null && a.lon != null);
  if (online) {
    layer.clearLayers();
    for (const a of located)
      L.circleMarker([a.lat, a.lon], {radius: 9, color: colors[a.type], fillOpacity: 0.7})
        .bindPopup(esc(a.type) + ' ' + a.conf.toFixed(2)).addTo(layer);
    if (located.length && !fitted) { map.fitBounds(located.map(a => [a.lat, a.lon]), {maxZoom: 18, padding: [30, 30]}); fitted = true; }
  } else {
    drawOffline(located);
  }
  document.getElementById('rows').innerHTML = data.map(a => {
    const img = a.snapshot ? '<a href="/snap/' + esc(a.snapshot) + '" target="_blank"><img src="/snap/' + esc(a.snapshot) + '"></a>' : '';
    return '<tr><td>' + a.id + '</td><td>' + esc(a.wall_time) + '</td><td><span class="badge ' + esc(a.type) + '">' + esc(a.type) + '</span></td><td>' +
      a.conf.toFixed(2) + '</td><td>' + fmt(a.lat) + '</td><td>' + fmt(a.lon) + '</td><td>' + img + '</td></tr>';
  }).join('');
}
refresh(); setInterval(refresh, 2000);
</script></body></html>"""


def main():
    host = os.environ.get("GS_HOST", "0.0.0.0")
    port = int(os.environ.get("GS_PORT", "5000"))
    data_dir = os.environ.get("GS_DATA_DIR") or None
    targets = os.environ.get("GS_BEACON_TARGETS", "255.255.255.255,10.42.0.255").split(",")
    beacon_port = int(os.environ.get("GS_BEACON_PORT", str(DEFAULT_BEACON_PORT)))
    app = create_app(data_dir, link_key=os.environ.get("GS_LINK_KEY", ""))
    Beacon(port, targets, beacon_port=beacon_port).start()
    print("Ground station on http://localhost:%d  (host %s, %s)" % (port, socket.gethostname(), host))
    print("Beacon: UDP %d -> %s" % (beacon_port, ", ".join(targets)))
    app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
