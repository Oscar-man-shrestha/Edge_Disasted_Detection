"""Drone AlertStore -> real HTTP -> ground station, including restart and GPS-less alerts."""
import os
import threading

import numpy as np
import pytest

import config

pytest.importorskip("flask")
pytest.importorskip("requests")


@pytest.fixture
def station(tmp_path, monkeypatch):
    import app as gs
    from werkzeug.serving import make_server
    monkeypatch.setattr(gs, "SNAP_DIR", str(tmp_path / "gs"))
    monkeypatch.setattr(gs, "DB_PATH", str(tmp_path / "gs" / "station.db"))
    monkeypatch.setattr(gs, "_db", None)
    srv = make_server("127.0.0.1", 0, gs.app, threaded=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setattr(config, "SERVER_URL", "http://127.0.0.1:%d/alert" % srv.server_port)
    yield gs
    srv.shutdown()


def det(t, c):
    return {"type": t, "conf": c, "box": [10, 10, 50, 50]}


FRAME = np.zeros((360, 640, 3), np.uint8)


def alerts(gs):
    return gs.app.test_client().get("/alerts.json").get_json()


def test_offline_then_online(tmp_config, monkeypatch):
    from alert_store import AlertStore
    monkeypatch.setattr(config, "SERVER_URL", "http://127.0.0.1:9/alert")   # nothing listens
    st = AlertStore()
    st.maybe_add(det("fire", .8), FRAME, 1.0, 12.97, 77.59)
    assert st.forward_pending() == (0, 1)


def test_cooldown_and_person_threshold(tmp_config):
    from alert_store import AlertStore
    st = AlertStore()
    assert st.maybe_add(det("fire", .8), FRAME, 1.0, 1, 1)
    assert st.maybe_add(det("fire", .9), FRAME, 5.0, 1, 1) is None         # inside cooldown
    assert st.maybe_add(det("fire", .9), FRAME, 12.0, 1, 1)                 # after cooldown
    assert st.maybe_add(det("person", .4), FRAME, 1.0, 1, 1) is None        # below PERSON_ALERT_CONF


def test_send_priority_missing_snapshot_dedupe_and_restart(tmp_config, station):
    from alert_store import AlertStore
    st = AlertStore()
    st.maybe_add(det("smoke", .6), FRAME, 1.0, 12.97, 77.59)
    st.maybe_add(det("fire", .8), FRAME, 2.0, 12.97, 77.59)
    st.maybe_add(det("person", .9), FRAME, 3.0, float("nan"), float("nan"))  # no GPS fix
    os.remove(st.db.execute("SELECT snapshot FROM alerts WHERE type='smoke'").fetchone()[0])

    assert st.forward_pending() == (3, 0)
    got = alerts(station)
    assert [a["type"] for a in got] == ["person", "fire", "smoke"]
    person = got[0]
    assert person["lat"] is None and person["lon"] is None
    assert got[2]["snapshot"] is None and got[1]["snapshot"]

    st.db.execute("UPDATE alerts SET sent=0")                 # reply "lost": resend all
    st.db.commit()
    assert st.forward_pending() == (3, 0)
    assert len(alerts(station)) == 3

    station._db.close()                                       # ground station restart
    station._db = None
    assert len(alerts(station)) == 3
