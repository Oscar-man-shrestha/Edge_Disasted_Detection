import os
import time
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__)
BASE = os.path.dirname(os.path.abspath(__file__))
SNAP_DIR = os.path.join(BASE, "received")
os.makedirs(SNAP_DIR, exist_ok=True)

PRIORITY = {"person": 1, "fire": 2, "smoke": 3}
alerts = []          # kept in memory; snapshots are saved to disk


@app.route("/alert", methods=["POST"])
def receive():
    typ = request.form.get("type", "")
    if typ not in PRIORITY:
        return jsonify(error="bad type"), 400
    try:
        entry = {
            "id": len(alerts) + 1,
            "type": typ,
            "conf": float(request.form["conf"]),
            "lat": float(request.form["lat"]),
            "lon": float(request.form["lon"]),
            "video_time": float(request.form.get("video_time", 0)),
            "wall_time": request.form.get("wall_time", "")[:40],
            "received": time.strftime("%H:%M:%S"),
            "snapshot": None,
        }
    except (KeyError, ValueError):
        return jsonify(error="bad fields"), 400

    f = request.files.get("snapshot")
    if f:
        name = f"{entry['id']}_{typ}.jpg"
        f.save(os.path.join(SNAP_DIR, name))
        entry["snapshot"] = name
    alerts.append(entry)
    print(f"[server] alert #{entry['id']} {typ} {entry['conf']:.2f} @ {entry['lat']:.6f},{entry['lon']:.6f}")
    return jsonify(ok=True), 200


@app.route("/alerts.json")
def alerts_json():
    ordered = sorted(alerts, key=lambda a: (PRIORITY[a["type"]], -a["id"]))
    return jsonify(ordered)


@app.route("/snap/<path:name>")
def snap(name):
    return send_from_directory(SNAP_DIR, name)


PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>Ground Station</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  body { font-family: system-ui, sans-serif; margin: 0; background: #111; color: #eee; }
  h1 { margin: 0; padding: 12px 16px; font-size: 18px; background: #1b1b1b; }
  #map { height: 340px; }
  table { width: 100%; border-collapse: collapse; }
  th, td { padding: 8px 12px; border-bottom: 1px solid #2a2a2a; text-align: left; font-size: 14px; }
  img { height: 48px; border-radius: 4px; }
  .badge { padding: 2px 8px; border-radius: 10px; font-weight: 600; color: #000; }
  .person { background: #4da3ff; } .fire { background: #ff6b3d; } .smoke { background: #b0b0b0; }
</style></head>
<body>
<h1>Drone Ground Station <span id="count" style="opacity:.6"></span></h1>
<div id="map"></div>
<table><thead><tr><th>#</th><th>Time</th><th>Type</th><th>Conf</th><th>Lat</th><th>Lon</th><th>Snapshot</th></tr></thead>
<tbody id="rows"></tbody></table>
<script>
const map = L.map('map').setView([12.9715, 77.5905], 17);
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom: 19, attribution: '&copy; OpenStreetMap'}).addTo(map);
const layer = L.layerGroup().addTo(map);
const colors = {person: '#4da3ff', fire: '#ff6b3d', smoke: '#b0b0b0'};
let fitted = false;

function esc(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

async function refresh() {
  let data;
  try { data = await (await fetch('/alerts.json')).json(); } catch (e) { return; }
  document.getElementById('count').textContent = '(' + data.length + ' alerts)';
  layer.clearLayers();
  const rows = data.map(a => {
    L.circleMarker([a.lat, a.lon], {radius: 9, color: colors[a.type], fillOpacity: 0.7})
      .bindPopup(esc(a.type) + ' ' + a.conf.toFixed(2)).addTo(layer);
    const img = a.snapshot ? '<a href="/snap/' + esc(a.snapshot) + '" target="_blank"><img src="/snap/' + esc(a.snapshot) + '"></a>' : '';
    return '<tr><td>' + a.id + '</td><td>' + esc(a.wall_time) + '</td><td><span class="badge ' + esc(a.type) + '">' + esc(a.type) + '</span></td><td>' +
      a.conf.toFixed(2) + '</td><td>' + a.lat.toFixed(6) + '</td><td>' + a.lon.toFixed(6) + '</td><td>' + img + '</td></tr>';
  });
  document.getElementById('rows').innerHTML = rows.join('');
  if (data.length && !fitted) { map.fitBounds(data.map(a => [a.lat, a.lon]), {maxZoom: 18, padding: [30, 30]}); fitted = true; }
}
refresh(); setInterval(refresh, 2000);
</script></body></html>"""


@app.route("/")
def index():
    return PAGE


if __name__ == "__main__":
    # GS_HOST=0.0.0.0 makes the station reachable from the Jetson over the network.
    app.run(host=os.environ.get("GS_HOST", "127.0.0.1"),
            port=int(os.environ.get("GS_PORT", "5000")), debug=False)