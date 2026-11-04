import csv
import io
import json
import xml.etree.ElementTree as ET

import pytest

from app import create_app
from exports import report_context, to_csv, to_geojson, to_kml

MISSION = {"id": 1, "name": "Mission 1", "started_at": "2026-11-05 10:00:00", "ended_at": None}


def A(i, typ, lat=12.97, lon=77.59, status="new", note=None, wall="2026-11-05 10:0%d:00"):
    return {"id": i, "mission_id": 1, "drone_id": "nano", "drone_alert_id": str(i), "type": typ,
            "conf": 0.8, "lat": lat, "lon": lon, "video_time": 1.0, "wall_time": wall % i,
            "received": "10:00:00", "snapshot": None, "status": status, "note": note,
            "acked_at": None, "resolved_at": None}


ALERTS = [A(1, "fire", note="near road, east side"), A(2, "person", lat=None, lon=None),
          A(3, "smoke", status="resolved", note="a < b & c")]
TRACK = [{"t": 0.0, "lat": 12.970, "lon": 77.59, "alt_m": None, "drone_id": "nano"},
         {"t": 30.0, "lat": 12.971, "lon": 77.59, "alt_m": None, "drone_id": "nano"}]


def test_csv_rows_and_header():
    rows = list(csv.reader(io.StringIO(to_csv(ALERTS))))
    assert rows[0] == ["id", "mission_id", "type", "conf", "status", "lat", "lon",
                       "wall_time", "received", "note", "snapshot"]
    assert len(rows) == 4
    assert rows[1][9] == "near road, east side"


def test_geojson_valid_and_skips_unlocated():
    gj = json.loads(json.dumps(to_geojson(ALERTS, TRACK)))
    pts = [f for f in gj["features"] if f["geometry"]["type"] == "Point"]
    lines = [f for f in gj["features"] if f["geometry"]["type"] == "LineString"]
    assert gj["type"] == "FeatureCollection"
    assert len(pts) == 2 and len(lines) == 1
    assert lines[0]["properties"]["kind"] == "track"
    assert pts[0]["geometry"]["coordinates"] == [77.59, 12.97]       # GeoJSON is lon, lat


def test_kml_parses():
    root = ET.fromstring(to_kml(MISSION, ALERTS, TRACK))
    ns = {"k": "http://www.opengis.net/kml/2.2"}
    assert len(root.findall(".//k:Placemark", ns)) == 3              # 2 located + track
    assert {s.get("id") for s in root.findall(".//k:Style", ns)} >= {"person", "fire", "smoke"}
    assert "a < b & c" in "".join(root.itertext())


def test_report_context_numbers():
    ctx = report_context(MISSION, ALERTS, TRACK)
    assert ctx["distance_m"] == pytest.approx(111.32, rel=1e-3)
    assert ctx["duration_s"] == 30.0
    assert ctx["counts"]["fire"]["total"] == 1 and ctx["counts"]["smoke"]["resolved"] == 1
    assert ctx["first_detection"]["person"] == "2026-11-05 10:02:00"
    assert ctx["bbox"] == [12.970, 77.59, 12.971, 77.59]


def test_export_routes(tmp_path):
    c = create_app(str(tmp_path / "gs"), watcher=False).test_client()
    c.post("/alert", data={"alert_id": "1", "type": "fire", "conf": "0.9", "lat": "12.97",
                           "lon": "77.59", "wall_time": "w1"})
    for fmt, mime in [("csv", "text/csv"), ("geojson", "application/geo+json"),
                      ("kml", "application/vnd.google-earth.kml+xml")]:
        r = c.get("/api/missions/1/export.%s" % fmt)
        assert r.status_code == 200 and r.mimetype == mime
        assert "attachment" in r.headers["Content-Disposition"]
        assert "mission-1.%s" % fmt in r.headers["Content-Disposition"]
    rep = c.get("/report/1")
    assert rep.status_code == 200 and b"Mission 1" in rep.data
    assert c.get("/api/missions/1/export.exe").status_code == 404
    assert c.get("/report/99").status_code == 404
    assert c.get("/api/missions/99/export.csv").status_code == 404


# ---------------------------------------------------------------- tiles
from flask import Flask  # noqa: E402

from tiles import MAX_PREFETCH, main as tiles_main, tile_range, tiles_blueprint  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\nfake"


def tile_client(tmp_path, fetch):
    app = Flask(__name__)
    app.register_blueprint(tiles_blueprint(str(tmp_path / "tiles"), fetch=fetch))
    return app.test_client()


def test_tile_served_from_cache_without_fetch(tmp_path):
    p = tmp_path / "tiles" / "15" / "23400" / "15200.png"
    p.parent.mkdir(parents=True)
    p.write_bytes(PNG)

    def boom(z, x, y):
        raise AssertionError("should not fetch")
    r = tile_client(tmp_path, boom).get("/tiles/15/23400/15200.png")
    assert r.status_code == 200 and r.data == PNG and r.mimetype == "image/png"


def test_tile_fetched_then_cached(tmp_path):
    calls = []

    def fetch(z, x, y):
        calls.append((z, x, y))
        return PNG
    c = tile_client(tmp_path, fetch)
    assert c.get("/tiles/3/2/1.png").data == PNG
    assert c.get("/tiles/3/2/1.png").data == PNG
    assert calls == [(3, 2, 1)]
    assert (tmp_path / "tiles" / "3" / "2" / "1.png").read_bytes() == PNG


def test_tile_offline_404(tmp_path):
    assert tile_client(tmp_path, lambda z, x, y: None).get("/tiles/3/2/1.png").status_code == 404


def test_tile_bad_coords_404(tmp_path):
    c = tile_client(tmp_path, lambda z, x, y: PNG)
    assert c.get("/tiles/a/b/c.png").status_code == 404
    assert c.get("/tiles/5/99999/1.png").status_code == 404     # x >= 2**z
    assert c.get("/tiles/20/1/1.png").status_code == 404        # beyond zoom 19


def test_tile_range_counts():
    tiles = tile_range(12.970, 77.590, 12.973, 77.5915, 17, 17)
    xs = {x for _, x, _ in tiles}
    ys = {y for _, _, y in tiles}
    assert len(tiles) == len(xs) * len(ys) and 1 <= len(tiles) <= 9
    assert all(z == 17 for z, _, _ in tiles)
    assert len(tile_range(12.970, 77.590, 12.973, 77.5915, 14, 15)) <= 4


def test_prefetch_refuses_too_many_and_zoom_19(capsys):
    assert MAX_PREFETCH == 3000
    assert tiles_main(["prefetch", "--bbox", "12,77,13,78", "--zoom", "14-18", "--dry-run"]) == 2
    assert tiles_main(["prefetch", "--bbox", "12.97,77.59,12.971,77.591", "--zoom", "19",
                       "--dry-run"]) == 2
    assert tiles_main(["prefetch", "--bbox", "12.97,77.59,12.971,77.591", "--zoom", "16-17",
                       "--dry-run"]) == 0


def test_report_counts_acknowledged_as_open(tmp_path):
    c = create_app(str(tmp_path / "gs"), watcher=False).test_client()
    c.post("/alert", data={"alert_id": "1", "type": "person", "conf": "0.9", "lat": "12.97",
                           "lon": "77.59", "wall_time": "w1"})
    c.post("/api/alerts/1", json={"status": "acknowledged"})
    html = c.get("/report/1").get_data(as_text=True)
    assert "0 resolved · 1 open" in html
