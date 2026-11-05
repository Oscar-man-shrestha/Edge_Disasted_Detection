import sqlite3

import pytest

from store import Store


def alert_fields(i=1, wall="2026-11-05 10:00:00", typ="fire", lat=12.97, lon=77.59):
    return {"drone_id": "nano", "drone_alert_id": str(i), "type": typ, "conf": 0.8,
            "lat": lat, "lon": lon, "video_time": 1.0, "wall_time": wall}


@pytest.fixture
def st(tmp_path):
    return Store(str(tmp_path / "station.db"))


def test_mission_created_on_first_use(st):
    m = st.current_mission()
    assert m["id"] == 1 and m["ended_at"] is None
    assert st.current_mission()["id"] == 1


def test_new_mission_closes_previous(st):
    old = st.current_mission()
    new = st.new_mission("Survey B")
    assert new["id"] > old["id"] and new["name"] == "Survey B"
    closed = [m for m in st.missions() if m["id"] == old["id"]][0]
    assert closed["ended_at"] is not None
    assert st.current_mission()["id"] == new["id"]


def test_add_alert_dedupes_and_keeps_status(st):
    a, created = st.add_alert(alert_fields())
    assert created and a["status"] == "new" and a["mission_id"] == 1
    st.update_alert(a["id"], status="acknowledged")
    b, created2 = st.add_alert(alert_fields())
    assert created2 is False
    assert b["id"] == a["id"] and b["status"] == "acknowledged"


def test_update_alert_timestamps(st):
    a, _ = st.add_alert(alert_fields())
    acked = st.update_alert(a["id"], status="acknowledged", note="team sent")
    assert acked["acked_at"] and acked["note"] == "team sent" and acked["resolved_at"] is None
    res = st.update_alert(a["id"], status="resolved")
    assert res["resolved_at"] and res["note"] == "team sent"
    with pytest.raises(ValueError):
        st.update_alert(a["id"], status="bogus")
    assert st.update_alert(9999, status="resolved") is None


def test_track_thinning(st):
    assert st.add_track_point("nano", 100.0, 12.970000, 77.59, None) is True
    assert st.add_track_point("nano", 101.0, 12.970009, 77.59, None) is False   # ~1 m, 1 s
    assert st.add_track_point("nano", 102.0, 12.970020, 77.59, None) is True    # ~2.2 m
    assert st.add_track_point("nano", 107.5, 12.970020, 77.59, None) is True    # same place, 5.5 s
    assert len(st.track(st.current_mission()["id"])) == 3


def test_migrates_v1_station_db(tmp_path):
    path = str(tmp_path / "station.db")
    con = sqlite3.connect(path)
    con.execute("""CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            drone_alert_id TEXT, type TEXT, conf REAL, lat REAL, lon REAL,
            video_time REAL, wall_time TEXT, received TEXT, snapshot TEXT)""")
    con.execute("CREATE UNIQUE INDEX IF NOT EXISTS dedupe ON alerts(drone_alert_id, wall_time)")
    con.execute("INSERT INTO alerts (drone_alert_id,type,conf,lat,lon,video_time,wall_time,received,snapshot) "
                "VALUES ('1','fire',0.8,12.97,77.59,1.0,'w1','10:00:00','1_fire.jpg')")
    con.execute("INSERT INTO alerts (drone_alert_id,type,conf,lat,lon,video_time,wall_time,received,snapshot) "
                "VALUES ('2','person',0.9,NULL,NULL,2.0,'w2','10:00:01',NULL)")
    con.commit()
    con.close()
    st = Store(path)
    rows = st.alerts(1)
    assert [r["type"] for r in rows] == ["fire", "person"]
    assert all(r["status"] == "new" and r["mission_id"] == 1 for r in rows)
    assert rows[0]["snapshot"] == "1_fire.jpg"


def test_track_ignores_non_finite(st):
    assert st.add_track_point("nano", 1.0, float("nan"), 77.59, None) is False
    assert st.add_track_point("nano", 1.0, 12.97, float("inf"), None) is False
    assert st.track(st.current_mission()["id"]) == []


# ---------------------------------------------------------------- UI v3: telemetry log, epochs
import math  # noqa: E402
import time  # noqa: E402

V2_TELEMETRY = {"drone_id": "nano", "gps": {"fix": True, "lat": 12.97, "lon": 77.59, "alt_m": 900.0,
                                            "speed_mps": 4.5, "course_deg": 90.0, "sats": 9},
                "pipeline": {"state": "active", "fps": 2.0, "stage2_runs": 5, "stage2_skipped": 3},
                "system": {"power_mw": 6100, "cpu_temp_c": 51.0, "gpu_temp_c": 49.5,
                           "cpu_load_pct": 60, "gpu_load_pct": 70}}


def test_mission_has_epoch_times(st):
    m = st.current_mission()
    assert abs(m["started_ts"] - time.time()) < 2 and m["ended_ts"] is None
    st.new_mission()
    old = [x for x in st.missions() if x["id"] == m["id"]][0]
    assert old["ended_ts"] >= old["started_ts"]


def test_alert_received_at_set(st):
    a, _ = st.add_alert(alert_fields())
    assert isinstance(a["received_at"], float) and abs(a["received_at"] - time.time()) < 2


def test_reopen_clears_resolved_at(st):
    a, _ = st.add_alert(alert_fields())
    st.update_alert(a["id"], status="resolved")
    r = st.update_alert(a["id"], status="acknowledged")
    assert r["resolved_at"] is None and r["acked_at"] is not None


def test_telemetry_sample_throttle(st):
    for t in (100.0, 102.0, 105.5, 106.0):
        st.add_telemetry_sample("nano", t, V2_TELEMETRY)
    rows = st.telemetry_log(st.current_mission()["id"])
    assert [r["t"] for r in rows] == [100.0, 105.5]
    r = rows[0]
    assert (r["lat"], r["fps"], r["power_mw"], r["fix"], r["state"]) == (12.97, 2.0, 6100, 1, "active")
    assert r["stage2_runs"] == 5 and r["course_deg"] == 90.0


def test_telemetry_sample_nonfinite_to_null(st):
    bad = {"gps": {"fix": True, "lat": float("nan"), "lon": 77.59}, "system": {"power_mw": "x"}}
    assert st.add_telemetry_sample("nano", 1.0, bad) is True
    r = st.telemetry_log(st.current_mission()["id"])[0]
    assert r["lat"] is None and r["power_mw"] is None and r["lon"] == 77.59


def test_migrates_v2_station_db(tmp_path):
    path = str(tmp_path / "station.db")
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE missions (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, started_at TEXT, ended_at TEXT)")
    con.execute("""CREATE TABLE alerts (id INTEGER PRIMARY KEY AUTOINCREMENT, drone_alert_id TEXT, type TEXT,
        conf REAL, lat REAL, lon REAL, video_time REAL, wall_time TEXT, received TEXT, snapshot TEXT,
        mission_id INTEGER, drone_id TEXT, status TEXT DEFAULT 'new', note TEXT, acked_at TEXT, resolved_at TEXT)""")
    con.execute("CREATE UNIQUE INDEX dedupe ON alerts(drone_alert_id, wall_time)")
    con.execute("CREATE TABLE track (id INTEGER PRIMARY KEY AUTOINCREMENT, mission_id INTEGER, drone_id TEXT, t REAL, lat REAL, lon REAL, alt_m REAL)")
    con.execute("INSERT INTO missions (name, started_at) VALUES ('Mission 1', '2026-11-05 10:00:00')")
    con.execute("INSERT INTO alerts (drone_alert_id,type,conf,wall_time,mission_id,status) VALUES ('1','fire',0.8,'w1',1,'new')")
    con.commit()
    con.close()
    st = Store(path)
    assert st.alerts(1)[0]["received_at"] is None
    assert st.current_mission()["started_ts"] == time.mktime(time.strptime("2026-11-05 10:00:00", "%Y-%m-%d %H:%M:%S"))
    assert st.telemetry_log(1) == []
