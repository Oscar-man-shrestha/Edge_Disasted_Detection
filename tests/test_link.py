"""Drone link: discovery, telemetry, preview and alert delivery to a real station."""
import socket
import threading
import time

import cv2
import numpy as np
import pytest

import config


def free_udp_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def wait_for(cond, timeout=3.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.05)
    return False


@pytest.fixture
def fast_link(monkeypatch):
    for name in ("TELEMETRY_INTERVAL_SEC", "PREVIEW_INTERVAL_SEC", "ALERT_FORWARD_INTERVAL_SEC"):
        monkeypatch.setattr(config, name, 0.1)
    monkeypatch.setattr(config, "LINK_KEY", "")


@pytest.fixture
def station(tmp_path):
    from werkzeug.serving import make_server
    from app import create_app
    app = create_app(str(tmp_path / "gs"), watcher=False)
    srv = make_server("127.0.0.1", 0, app, threaded=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    app.url = "http://127.0.0.1:%d" % srv.server_port
    yield app
    srv.shutdown()


FRAME = np.full((360, 640, 3), 90, np.uint8)
GATE = {"trigger": True, "ms": 4.0}
FIRE = [{"type": "fire", "conf": 0.8, "box": [100, 100, 300, 250]}]


def test_station_finder_from_beacon():
    from discovery import Beacon
    from link import StationFinder
    port = free_udp_port()
    finder = StationFinder(port=port).start()
    b = Beacon(5000, ["127.0.0.1"], beacon_port=port, interval=0.1).start()
    try:
        assert wait_for(lambda: finder.url() == "http://127.0.0.1:5000", 2.0)
    finally:
        b.stop()
        finder.stop()


def test_station_finder_forgets_after_10s():
    from link import StationFinder
    f = StationFinder(port=free_udp_port())
    f._on_beacon("10.42.0.20", {"service": "edge-gs", "v": 1, "port": 5000}, now=100.0)
    assert f.url(now=109.0) == "http://10.42.0.20:5000"
    assert f.url(now=111.0) is None


def test_station_finder_keeps_current_station():
    from link import StationFinder
    f = StationFinder(port=free_udp_port())
    f._on_beacon("10.42.0.20", {"service": "edge-gs", "v": 1, "port": 5000}, now=100.0)
    f._on_beacon("10.42.0.99", {"service": "edge-gs", "v": 1, "port": 5000}, now=101.0)
    assert f.url(now=102.0) == "http://10.42.0.20:5000"
    f._on_beacon("10.42.0.99", {"service": "edge-gs", "v": 1, "port": 5000}, now=112.0)
    assert f.url(now=112.5) == "http://10.42.0.99:5000"
    f._on_beacon("10.42.0.5", {"service": "other"}, now=113.0)     # ignored
    assert f.url(now=113.0) == "http://10.42.0.99:5000"


def test_fixed_url_strips_alert():
    from link import StationFinder
    assert StationFinder(fixed_url="http://h:5000/alert").url() == "http://h:5000"
    assert StationFinder(fixed_url="http://h:5000/").url() == "http://h:5000"


def test_link_delivers_everything(tmp_config, fast_link, station):
    from alert_store import AlertStore
    from gps_sim import GPSSim
    from link import DroneLink, LinkState, StationFinder
    AlertStore().maybe_add(FIRE[0], FRAME, 1.0, 12.97, 77.59)
    state = LinkState()
    for i in range(5):
        state.frame(FRAME, GATE, ran_stage2=True, stage2_ms=120.0, t=float(i))
    state.detections(FIRE, time.time())
    link = DroneLink(state, GPSSim(), StationFinder(fixed_url=station.url)).start()
    try:
        live = station.config["LIVE"]
        assert wait_for(lambda: live["telemetry"] is not None and live["preview_jpeg"] is not None)
        assert wait_for(lambda: len(station.config["STORE"].alerts()) == 1)
        tel = live["telemetry"]
        assert tel["gps"]["fix"] is True and tel["drone_id"] == config.DRONE_ID
        assert tel["pipeline"]["state"] == "active" and tel["pipeline"]["stage2_runs"] == 5
        assert tel["pipeline"]["last_detection"]["type"] == "fire"
        assert live["preview_stage2"] is True
        assert wait_for(lambda: station.config["LIVE"]["telemetry"]["link"]["alerts_buffered"] == 0)
    finally:
        link.stop()


def test_link_offline_buffers_and_never_blocks(tmp_config, fast_link):
    from alert_store import AlertStore
    from gps_sim import GPSSim
    from link import DroneLink, LinkState, StationFinder
    AlertStore().maybe_add(FIRE[0], FRAME, 1.0, 12.97, 77.59)
    state = LinkState()
    link = DroneLink(state, GPSSim(), StationFinder(fixed_url="http://127.0.0.1:9")).start()
    t0 = time.perf_counter()
    for i in range(200):
        state.frame(FRAME, GATE, ran_stage2=False, stage2_ms=None, t=float(i))
    assert time.perf_counter() - t0 < 0.05
    time.sleep(0.5)
    assert AlertStore().counts()["buffered"] == 1
    t1 = time.time()
    link.stop(flush_timeout=5.0)
    assert time.time() - t1 < 6.0


def test_link_key_header_sent(tmp_config, fast_link, tmp_path, monkeypatch):
    from werkzeug.serving import make_server
    from alert_store import AlertStore
    from app import create_app
    from gps_sim import GPSSim
    from link import DroneLink, LinkState, StationFinder
    app = create_app(str(tmp_path / "keyed"), link_key="k", watcher=False)
    srv = make_server("127.0.0.1", 0, app, threaded=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = "http://127.0.0.1:%d" % srv.server_port
    try:
        AlertStore().maybe_add(FIRE[0], FRAME, 1.0, 12.97, 77.59)
        monkeypatch.setattr(config, "LINK_KEY", "wrong")
        link = DroneLink(LinkState(), GPSSim(), StationFinder(fixed_url=url)).start()
        time.sleep(0.6)
        link.stop()
        assert app.config["STORE"].alerts() == []
        monkeypatch.setattr(config, "LINK_KEY", "k")
        link = DroneLink(LinkState(), GPSSim(), StationFinder(fixed_url=url)).start()
        assert wait_for(lambda: len(app.config["STORE"].alerts()) == 1)
        link.stop()
    finally:
        srv.shutdown()


def test_preview_size_and_boxes():
    from link import build_preview
    jpg = build_preview(FRAME, FIRE, 480, 60)
    img = cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_COLOR)
    assert img.shape == (270, 480, 3)
    b, g, r = [int(v) for v in img[75, 120]]          # left edge of the scaled box (100*0.75)
    assert r > 150 and g < 120 and b < 120
    plain = cv2.imdecode(np.frombuffer(build_preview(FRAME, [], 480, 60), np.uint8), 1)
    assert abs(int(plain[75, 120][2]) - 90) < 10


def test_run_pipeline_end_to_end(tmp_config, fast_link, station, tmp_path, monkeypatch):
    """Real run_pipeline.py on a synthetic video, stub YOLO, real station over HTTP."""
    import os
    import runpy
    import stage2_detector
    from alert_store import AlertStore

    vid = str(tmp_path / "synth.mp4")
    w = cv2.VideoWriter(vid, cv2.VideoWriter_fourcc(*"mp4v"), 25, (640, 360))
    for i in range(250):                                   # 4 s calm, then an orange blob
        f = np.zeros((360, 640, 3), np.uint8)
        if i >= 100:
            f[100:250, 200:400] = (0, 140, 255)
        w.write(f)
    w.release()

    class FakeDetector:
        def detect(self, frame):
            time.sleep(0.05)                               # pretend to be YOLO
            hit = frame[150, 300, 2] > 200
            return ([{"type": "fire", "conf": 0.7, "box": [200, 100, 400, 250]}] if hit else []), 50.0

    monkeypatch.setattr(stage2_detector, "Stage2Detector", FakeDetector)
    monkeypatch.setattr(config, "SOURCE", vid)
    monkeypatch.setattr(config, "SERVER_URL", station.url)
    monkeypatch.setattr(config, "GPS_MODE", "sim")
    runpy.run_path(os.path.join(os.path.dirname(os.path.dirname(__file__)), "run_pipeline.py"),
                   run_name="__main__")
    alerts = station.config["STORE"].alerts()
    assert [a["type"] for a in alerts] == ["fire"]
    assert station.config["LIVE"]["telemetry"] is not None
    assert station.config["LIVE"]["preview_jpeg"] is not None
    assert AlertStore().counts()["buffered"] == 0


def test_beacon_without_port_falls_back_to_5050():
    from link import StationFinder
    f = StationFinder(port=free_udp_port())
    f._on_beacon("10.42.0.20", {"service": "edge-gs", "v": 1}, now=100.0)
    assert f.url(now=100.5) == "http://10.42.0.20:5050"


def test_preview_interval_from_env(monkeypatch):
    import importlib
    monkeypatch.setenv("EDGE_PREVIEW_SEC", "0.5")
    try:
        assert importlib.reload(config).PREVIEW_INTERVAL_SEC == 0.5
        monkeypatch.setenv("EDGE_PREVIEW_SEC", "0.01")              # floor: never flood the link
        assert importlib.reload(config).PREVIEW_INTERVAL_SEC == 0.2
    finally:
        monkeypatch.delenv("EDGE_PREVIEW_SEC")
        importlib.reload(config)
    assert config.PREVIEW_INTERVAL_SEC == 1.5


def test_link_key_from_env_then_file(tmp_path, monkeypatch):
    import importlib
    key = tmp_path / ".link_key"
    key.write_text("  s3cret\n")
    monkeypatch.setattr(config, "LINK_KEY_FILE", str(key))
    monkeypatch.delenv("EDGE_LINK_KEY", raising=False)
    assert config.read_link_key() == "s3cret"
    monkeypatch.setenv("EDGE_LINK_KEY", "fromenv")
    assert config.read_link_key() == "fromenv"
    monkeypatch.setenv("EDGE_LINK_KEY", "")                  # set but empty: key explicitly off
    assert config.read_link_key() == ""
    monkeypatch.delenv("EDGE_LINK_KEY")
    key.unlink()
    assert config.read_link_key() == ""


def test_sample_interval_from_env(monkeypatch):
    import importlib
    try:
        monkeypatch.setenv("EDGE_SAMPLE_SEC", "0.25")
        assert importlib.reload(config).SAMPLE_INTERVAL_SEC == 0.25
        monkeypatch.setenv("EDGE_SAMPLE_SEC", "0.01")             # floor: protect the Nano
        assert importlib.reload(config).SAMPLE_INTERVAL_SEC == 0.2
    finally:
        monkeypatch.delenv("EDGE_SAMPLE_SEC", raising=False)
        importlib.reload(config)
    assert config.SAMPLE_INTERVAL_SEC == 0.5


def test_sim_remote_steers_a_simulated_drone_end_to_end(tmp_config, fast_link, station, monkeypatch):
    """Dashboard -> station -> telemetry reply -> drone: the simulated drone turns and speeds up."""
    from gps_sim import GPSSim
    from link import DroneLink, LinkState, StationFinder
    monkeypatch.setattr(config, "GPS_MODE", "sim")
    state = LinkState()
    state.frame(FRAME, GATE, ran_stage2=False, t=10.0)
    gps = GPSSim()
    c = station.test_client()
    assert c.post("/api/sim", json={"mode": "manual", "heading": 90, "speed": 7}).status_code == 200
    link = DroneLink(state, gps, StationFinder(fixed_url=station.url)).start()
    try:
        live = station.config["LIVE"]
        assert wait_for(lambda: (live["telemetry"] or {}).get("gps", {}).get("control") == "manual")
        g = live["telemetry"]["gps"]
        assert g["course_deg"] == 90 and g["speed_mps"] == 7
    finally:
        link.stop()


def test_sim_remote_ignored_by_a_real_gps(tmp_config, fast_link, station, monkeypatch):
    """A drone on a real GPS must never apply simulator commands."""
    from link import DroneLink, LinkState, StationFinder
    monkeypatch.setattr(config, "GPS_MODE", "nmea")
    calls = []

    class RealGPS:                             # has control() by accident: must still be ignored
        def status(self, t=None):
            return {"mode": "nmea", "fix": True, "lat": 1.0, "lon": 2.0}

        def control(self, *a):
            calls.append(a)

    station.test_client().post("/api/sim", json={"mode": "manual", "heading": 90, "speed": 7})
    link = DroneLink(LinkState(), RealGPS(), StationFinder(fixed_url=station.url)).start()
    try:
        assert wait_for(lambda: station.config["LIVE"]["telemetry"] is not None)
        time.sleep(0.3)
        assert calls == []
    finally:
        link.stop()
