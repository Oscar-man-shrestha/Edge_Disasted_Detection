import os
import sqlite3
import threading
import time
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__)
BASE = os.path.dirname(os.path.abspath(__file__))
SNAP_DIR = os.environ.get("GS_DATA_DIR", os.path.join(BASE, "received"))
DB_PATH = os.path.join(SNAP_DIR, "station.db")

PRIORITY = {"person": 1, "fire": 2, "smoke": 3}
_lock = threading.Lock()
_db = None


def db():
    """Alerts survive a ground-station restart (SQLite next to the snapshots)."""
    global _db
    if _db is None:
        os.makedirs(SNAP_DIR, exist_ok=True)
        _db = sqlite3.connect(DB_PATH, check_same_thread=False)
        _db.execute("""CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            drone_alert_id TEXT, type TEXT, conf REAL, lat REAL, lon REAL,
            video_time REAL, wall_time TEXT, received TEXT, snapshot TEXT)""")
        # the drone resends when a reply is lost; this makes the resend a no-op
        _db.execute("CREATE UNIQUE INDEX IF NOT EXISTS dedupe ON alerts(drone_alert_id, wall_time)")
        _db.commit()
    return _db


def _opt_float(v):
    """lat/lon may be empty when the drone had no GPS fix."""
    if v is None or v.strip().lower() in ("", "none", "nan"):
        return None
    return float(v)


@app.route("/alert", methods=["POST"])
def receive():
    typ = request.form.get("type", "")
    if typ not in PRIORITY:
        return jsonify(error="bad type"), 400
    try:
        conf = float(request.form["conf"])
        lat = _opt_float(request.form.get("lat"))
        lon = _opt_float(request.form.get("lon"))
        video_time = float(request.form.get("video_time", 0))
    except (KeyError, ValueError):
        return jsonify(error="bad fields"), 400
    wall_time = request.form.get("wall_time", "")[:40]
    drone_id = request.form.get("alert_id")

    with _lock:
        con = db()
        if drone_id is not None:
            dup = con.execute("SELECT id FROM alerts WHERE drone_alert_id=? AND wall_time=?",
                              (drone_id, wall_time)).fetchone()
            if dup:
                return jsonify(ok=True, duplicate=True), 200
        cur = con.execute(
            "INSERT INTO alerts (drone_alert_id, type, conf, lat, lon, video_time, wall_time, received) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (drone_id, typ, conf, lat, lon, video_time, wall_time, time.strftime("%H:%M:%S")))
        new_id = cur.lastrowid
        f = request.files.get("snapshot")
        if f:
            name = f"{new_id}_{typ}.jpg"
            f.save(os.path.join(SNAP_DIR, name))
            con.execute("UPDATE alerts SET snapshot=? WHERE id=?", (name, new_id))
        con.commit()
    where = "no GPS fix" if lat is None else f"{lat:.6f},{lon:.6f}"
    print(f"[server] alert #{new_id} {typ} {conf:.2f} @ {where}")
    return jsonify(ok=True), 200


@app.route("/alerts.json")
def alerts_json():
    with _lock:
        rows = db().execute(
            "SELECT id, type, conf, lat, lon, video_time, wall_time, received, snapshot "
            "FROM alerts").fetchall()
    keys = ["id", "type", "conf", "lat", "lon", "video_time", "wall_time", "received", "snapshot"]
    alerts = [dict(zip(keys, r)) for r in rows]
    alerts.sort(key=lambda a: (PRIORITY[a["type"]], -a["id"]))
    return jsonify(alerts)


@app.route("/health")
def health():
    return jsonify(ok=True)


@app.route("/snap/<path:name>")
def snap(name):
    return send_from_directory(SNAP_DIR, name)


PAGE = """<!doctype html>
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


@app.route("/")
def index():
    return PAGE


if __name__ == "__main__":
    # GS_HOST=0.0.0.0 makes the station reachable from the Jetson over the network.
    app.run(host=os.environ.get("GS_HOST", "127.0.0.1"),
            port=int(os.environ.get("GS_PORT", "5000")), debug=False, threaded=True)
