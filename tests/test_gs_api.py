import io
import time

import cv2
import numpy as np
import pytest

from app import create_app, link_state


@pytest.fixture
def app(tmp_path):
    return create_app(str(tmp_path / "gs"))


@pytest.fixture
def client(app):
    return app.test_client()


def jpeg(w=64, h=36):
    ok, buf = cv2.imencode(".jpg", np.full((h, w, 3), 128, np.uint8))
    return buf.tobytes()


TELEM = {"drone_id": "nano", "seq": 1, "time": time.time() - 36000,       # drone clock 10 h off
         "gps": {"mode": "nmea", "fix": True, "lat": 12.97, "lon": 77.59, "sats": 9,
                 "speed_mps": 4.0, "course_deg": 90.0},
         "pipeline": {"state": "scanning", "fps": 2.0}, "system": {"power_mw": 5000},
         "link": {"alerts_buffered": 0}}


def post_alert(client, i=1, typ="fire", headers=None):
    return client.post("/alert", headers=headers or {}, data={
        "alert_id": str(i), "drone_id": "nano", "type": typ, "conf": "0.8",
        "lat": "12.97", "lon": "77.59", "video_time": "1.0", "wall_time": "w%d" % i})


def test_telemetry_accepted_and_state_live(client):
    assert client.post("/api/telemetry", json=TELEM).status_code == 200
    st = client.get("/api/state").get_json()
    assert st["link"]["state"] == "live"
    assert st["telemetry"]["gps"]["sats"] == 9
    assert len(st["track"]) == 1


def test_telemetry_without_gps_accepted(client):
    assert client.post("/api/telemetry", json={"drone_id": "x"}).status_code == 200
    assert client.post("/api/telemetry", json={"gps": None}).status_code == 200
    assert client.get("/api/state").get_json()["track"] == []


def test_telemetry_bad_json_400(client):
    assert client.post("/api/telemetry", data="not json",
                       content_type="application/json").status_code == 400
    assert client.post("/api/telemetry", json={"gps": "nope"}).status_code == 400
    assert client.post("/api/telemetry", json=[1, 2]).status_code == 400


def test_link_lost_after_3s():
    assert link_state({"received_at": None}, now=100.0)["state"] == "never"
    assert link_state({"received_at": 100.0}, now=102.0)["state"] == "live"
    lost = link_state({"received_at": 100.0}, now=103.5)
    assert lost["state"] == "lost" and lost["age_s"] == pytest.approx(3.5)


def test_preview_roundtrip(client):
    img = jpeg()
    r = client.post("/api/preview", data=img, content_type="image/jpeg",
                    headers={"X-Stage2-Active": "1", "X-Frame-Time": "123.5"})
    assert r.status_code == 200
    got = client.get("/api/preview.jpg")
    assert got.status_code == 200 and got.data == img
    assert client.get("/api/state").get_json()["preview"]["stage2"] is True


def test_preview_missing_404(client):
    assert client.get("/api/preview.jpg").status_code == 404


def test_preview_rejects_non_jpeg_and_oversize(client):
    png = cv2.imencode(".png", np.zeros((4, 4, 3), np.uint8))[1].tobytes()
    assert client.post("/api/preview", data=png, content_type="image/jpeg").status_code == 400
    big = b"\xff\xd8" + b"\x00" * 600000
    assert client.post("/api/preview", data=big, content_type="image/jpeg").status_code == 413


def test_alert_status_update_and_event(app, client):
    assert post_alert(client).status_code == 200
    aid = client.get("/api/state").get_json()["alerts"][0]["id"]
    q = app.config["BUS"].subscribe()
    r = client.post("/api/alerts/%d" % aid, json={"status": "acknowledged", "note": "team sent"})
    assert r.status_code == 200
    ev, data = q.get(timeout=1)
    assert ev == "alert_update" and data["alert"]["status"] == "acknowledged"
    assert client.get("/api/state").get_json()["alerts"][0]["note"] == "team sent"


def test_new_alert_published(app, client):
    q = app.config["BUS"].subscribe()
    post_alert(client, typ="person")
    ev, data = q.get(timeout=1)
    assert ev == "alert" and data["alert"]["type"] == "person"


def test_alert_update_unknown_and_bad_status(client):
    assert client.post("/api/alerts/999", json={"status": "resolved"}).status_code == 404
    post_alert(client)
    assert client.post("/api/alerts/1", json={"status": "bogus"}).status_code == 400


def test_link_key_required_when_set(tmp_path):
    c = create_app(str(tmp_path / "k"), link_key="k").test_client()
    assert c.post("/api/telemetry", json=TELEM).status_code == 401
    assert c.post("/api/preview", data=jpeg(), content_type="image/jpeg").status_code == 401
    assert post_alert(c).status_code == 401
    ok = {"X-Link-Key": "k"}
    assert c.post("/api/telemetry", json=TELEM, headers=ok).status_code == 200
    assert c.post("/api/preview", data=jpeg(), content_type="image/jpeg",
                  headers=ok).status_code == 200
    assert post_alert(c, headers=ok).status_code == 200
    assert c.get("/api/state").status_code == 200


def test_snapshot_served_with_relative_data_dir(tmp_path, monkeypatch):
    """GS_DATA_DIR=ground_station/received/live (relative) must still serve snapshots.
    Flask resolves relative paths against the app folder, not the working directory."""
    monkeypatch.chdir(tmp_path)
    c = create_app("rel/data", watcher=False).test_client()
    r = c.post("/alert", content_type="multipart/form-data", data={
        "alert_id": "1", "drone_id": "nano", "type": "person", "conf": "0.9",
        "lat": "12.97", "lon": "77.59", "video_time": "1.0", "wall_time": "w1",
        "snapshot": (io.BytesIO(jpeg()), "s.jpg")})
    assert r.status_code == 200
    got = c.get("/snap/1_person.jpg")
    assert got.status_code == 200 and got.data[:2] == b"\xff\xd8"


def test_snap_path_traversal_404(client, app):
    assert client.get("/snap/../station.db").status_code == 404
    assert client.get("/snap/%2e%2e/station.db").status_code == 404
    assert client.get("/snap/..%2fstation.db").status_code == 404
    assert client.get("/snap/station.db").status_code == 404
    assert client.get("/snap/station.db-wal").status_code == 404


def test_snapshot_saved_and_served(client):
    client.post("/alert", data={"alert_id": "7", "type": "fire", "conf": "0.9", "lat": "",
                                "lon": "", "wall_time": "w7",
                                "snapshot": (io.BytesIO(jpeg()), "x.jpg")},
                content_type="multipart/form-data")
    a = client.get("/api/state").get_json()["alerts"][0]
    assert a["lat"] is None and a["snapshot"]
    assert client.get("/snap/" + a["snapshot"]).status_code == 200


def test_new_mission_endpoint(app, client):
    q = app.config["BUS"].subscribe()
    r = client.post("/api/missions", json={"name": "Survey B"})
    assert r.status_code == 200
    new_id = r.get_json()["mission"]["id"]
    assert client.get("/api/state").get_json()["mission"]["id"] == new_id
    assert q.get(timeout=1)[0] == "mission"
    assert len(client.get("/api/missions").get_json()) == 2


def test_alerts_json_backcompat(client):
    post_alert(client, 1, "smoke")
    post_alert(client, 2, "person")
    assert [a["type"] for a in client.get("/alerts.json").get_json()] == ["person", "smoke"]


def test_health(client):
    assert client.get("/health").get_json()["ok"] is True


def test_dashboard_has_no_external_assets(tmp_path):
    import re
    ui = tmp_path / "ui"
    ui.mkdir()
    (ui / "index.html").write_text('<!doctype html><div id="root"></div>'
                                   '<script type="module" src="/static/app/assets/x.js"></script>')
    c = create_app(str(tmp_path / "gs"), watcher=False, ui_dir=str(ui)).test_client()
    html = c.get("/").get_data(as_text=True)
    refs = re.findall(r'(?:src|href)\s*=\s*"([^"]+)"', html)
    assert refs and not [u for u in refs if u.startswith(("http://", "https://", "//"))]


@pytest.mark.parametrize("gps", [
    {"fix": True, "lat": 1.0, "lon": 2.0, "course_deg": "0deg)\"><img src=x onerror=alert(1)>"},
    {"fix": True, "lat": float("nan"), "lon": 2.0},
    {"fix": True, "lat": 1.0, "lon": float("inf")},
    {"fix": True, "lat": True, "lon": 2.0},
    {"fix": "yes", "lat": 1.0, "lon": 2.0},
    {"sats": "nine"},
])
def test_telemetry_rejects_bad_gps_fields(client, gps):
    import json
    body = json.dumps({"drone_id": "x", "gps": gps})        # json.dumps allows NaN/Infinity
    r = client.post("/api/telemetry", data=body, content_type="application/json")
    assert r.status_code == 400
    st = client.get("/api/state").get_json()
    assert st["telemetry"] is None and st["track"] == []


def test_telemetry_null_gps_fields_still_ok(client):
    r = client.post("/api/telemetry", json={"gps": {"mode": "nmea", "fix": False, "lat": None,
                                                    "lon": None, "course_deg": None}})
    assert r.status_code == 200


# ---------------------------------------------------------------- UI v3: timeline, missions, built UI
def test_timeline_shape(app, client, monkeypatch):
    import store as store_mod
    monkeypatch.setattr(store_mod, "TELEMETRY_SAMPLE_S", 0)
    client.post("/api/telemetry", json=TELEM)
    time.sleep(0.01)
    client.post("/api/telemetry", json=TELEM)
    post_alert(client)
    tl = client.get("/api/missions/1/timeline").get_json()
    assert set(tl) >= {"mission", "server_time", "track", "telemetry", "alerts"}
    assert len(tl["telemetry"]) == 2
    assert isinstance(tl["alerts"][0]["received_at"], float)
    assert tl["mission"]["id"] == 1


def test_timeline_unknown_404(client):
    assert client.get("/api/missions/99/timeline").status_code == 404


def test_state_missions_have_epochs(client):
    st = client.get("/api/state").get_json()
    assert isinstance(st["mission"]["started_ts"], float)
    assert isinstance(st["missions"][0]["started_ts"], float)


def test_missions_list_counts_and_distance(client):
    for i, typ in enumerate(["fire", "fire", "person"], 1):
        post_alert(client, i, typ)
    for lat in (12.970, 12.971):
        body = dict(TELEM, gps={"fix": True, "lat": lat, "lon": 77.59})
        client.post("/api/telemetry", json=body)
    m = client.get("/api/missions").get_json()[0]
    assert m["alert_counts"] == {"person": 1, "fire": 2, "smoke": 0}
    assert m["distance_m"] == pytest.approx(111.32, rel=1e-3)


@pytest.mark.parametrize("path", ["/api/alerts/1", "/api/missions"])
@pytest.mark.parametrize("body", ["[1]", '"x"'])
def test_non_object_json_400(client, path, body):
    post_alert(client)
    r = client.post(path, data=body, content_type="application/json")
    assert r.status_code == 400


def test_index_serves_built_ui(tmp_path):
    ui = tmp_path / "ui"
    ui.mkdir()
    (ui / "index.html").write_text('<!doctype html><div id="root"></div>')
    c = create_app(str(tmp_path / "gs"), watcher=False, ui_dir=str(ui)).test_client()
    r = c.get("/")
    assert r.status_code == 200 and 'id="root"' in r.get_data(as_text=True)
    assert r.headers["Cache-Control"] == "no-cache"


def test_index_without_build_503(tmp_path):
    c = create_app(str(tmp_path / "gs"), watcher=False, ui_dir=str(tmp_path / "missing")).test_client()
    r = c.get("/")
    assert r.status_code == 503
    assert "npm ci && npm run build" in r.get_data(as_text=True)


def test_default_port_avoids_macos_airplay():
    """macOS AirPlay Receiver owns port 5000 (answers 403 AirTunes), so the station defaults to 5050."""
    import app as station
    assert station.DEFAULT_PORT == 5050
