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
