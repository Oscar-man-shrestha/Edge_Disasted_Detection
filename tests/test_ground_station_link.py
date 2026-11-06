"""Drone AlertStore -> real HTTP -> ground station, including restart and GPS-less alerts."""
import os
import threading

import numpy as np
import pytest

import config

pytest.importorskip("flask")
pytest.importorskip("requests")


class Station:
    def __init__(self, data_dir):
        from app import create_app
        self.data_dir = data_dir
        self.app = create_app(data_dir)


@pytest.fixture
def station(tmp_path, monkeypatch):
    from werkzeug.serving import make_server
    st = Station(str(tmp_path / "gs"))
    srv = make_server("127.0.0.1", 0, st.app, threaded=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    st.url = "http://127.0.0.1:%d" % srv.server_port
    yield st
    srv.shutdown()


def det(t, c):
    return {"type": t, "conf": c, "box": [10, 10, 50, 50]}


FRAME = np.zeros((360, 640, 3), np.uint8)


def alerts(gs):
    return gs.app.test_client().get("/alerts.json").get_json()


def test_offline_then_online(tmp_config, monkeypatch):
    from alert_store import AlertStore
    st = AlertStore()
    st.maybe_add(det("fire", .8), FRAME, 1.0, 12.97, 77.59)
    assert st.forward_pending("http://127.0.0.1:9", {}) == (0, 1)   # nothing listens


def test_one_alert_per_event_and_person_threshold(tmp_config, monkeypatch):
    """A fire/person seen continuously is ONE alert (event), not one every few seconds."""
    from alert_store import AlertStore
    monkeypatch.setattr(config, "EVENT_GAP_SEC", 30)
    monkeypatch.setattr(config, "ALERT_REPEAT_SEC", 60)
    st = AlertStore()
    assert st.maybe_add(det("fire", .8), FRAME, 1.0, 1, 1)
    for t in (5.0, 12.0, 25.0, 50.0):                                       # still the same fire
        assert st.maybe_add(det("fire", .9), FRAME, t, 1, 1) is None
    assert st.maybe_add(det("fire", .9), FRAME, 62.0, 1, 1)                 # long event: repeat
    assert st.maybe_add(det("fire", .9), FRAME, 70.0, 1, 1) is None
    assert st.maybe_add(det("fire", .9), FRAME, 101.0, 1, 1)                # gone > 30 s: new event
    assert st.maybe_add(det("person", .9), FRAME, 101.0, 1, 1)              # other types independent
    assert st.maybe_add(det("person", .4), FRAME, 1.0, 1, 1) is None        # below PERSON_ALERT_CONF


def test_weak_detection_does_not_extend_event(tmp_config, monkeypatch):
    """Below-threshold person sightings must not keep an event 'alive' forever."""
    from alert_store import AlertStore
    monkeypatch.setattr(config, "EVENT_GAP_SEC", 30)
    st = AlertStore()
    assert st.maybe_add(det("person", .9), FRAME, 0.0, 1, 1)
    for t in range(5, 60, 5):
        assert st.maybe_add(det("person", .3), FRAME, float(t), 1, 1) is None
    assert st.maybe_add(det("person", .9), FRAME, 61.0, 1, 1)


def test_send_priority_missing_snapshot_dedupe_and_restart(tmp_config, station):
    from alert_store import AlertStore
    st = AlertStore()
    st.maybe_add(det("smoke", .6), FRAME, 1.0, 12.97, 77.59)
    st.maybe_add(det("fire", .8), FRAME, 2.0, 12.97, 77.59)
    st.maybe_add(det("person", .9), FRAME, 3.0, float("nan"), float("nan"))  # no GPS fix
    os.remove(st.db.execute("SELECT snapshot FROM alerts WHERE type='smoke'").fetchone()[0])

    assert st.forward_pending(station.url, {}) == (3, 0)
    got = alerts(station)
    assert [a["type"] for a in got] == ["person", "fire", "smoke"]
    person = got[0]
    assert person["lat"] is None and person["lon"] is None
    assert got[2]["snapshot"] is None and got[1]["snapshot"]

    st.db.execute("UPDATE alerts SET sent=0")                 # reply "lost": resend all
    st.db.commit()
    assert st.forward_pending(station.url, {}) == (3, 0)
    assert len(alerts(station)) == 3

    restarted = Station(station.data_dir)                     # ground station restart
    assert len(alerts(restarted)) == 3


def test_clip_end_to_end(tmp_config, tmp_path, station):
    from alert_store import AlertStore
    from clip_recorder import ClipRecorder
    st = AlertStore()
    rec = ClipRecorder(before=1, after=1, clip_dir=str(tmp_path / "clips"))
    for i in range(3):
        rec.push(i * 0.5, FRAME)
    aid = st.maybe_add(det("fire", .8), FRAME, 1.0, 12.97, 77.59)
    rec.request(aid, 1.0)
    done = [c for i in range(3, 6) for c in rec.push(i * 0.5, FRAME)]
    st.set_clip(*done[0])
    assert st.forward_clips(station.url, {}) == (0, 1)             # alert itself not delivered yet
    assert st.forward_pending(station.url, {}) == (1, 0)
    assert st.forward_clips(station.url, {}) == (1, 0)
    a = alerts(station)[0]
    assert a["clip_frames"] == 5
    c = station.app.test_client()
    assert c.get("/clip/%d/4.jpg" % a["id"]).status_code == 200
