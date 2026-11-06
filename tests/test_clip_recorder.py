"""Short alert clips on the drone: what is recorded, kept, and forwarded."""
import os

import numpy as np
import pytest

import config


def frame(v):
    return np.full((360, 640, 3), v, np.uint8)


@pytest.fixture
def rec(tmp_path, monkeypatch):
    from clip_recorder import ClipRecorder
    return ClipRecorder(before=4, after=4, width=320, quality=60,
                        clip_dir=str(tmp_path / "clips"), keep=3)


def run(rec, t_from, t_to, step=0.5):
    done, t = [], t_from
    while t <= t_to + 1e-9:
        done += rec.push(t, frame(int(t * 10) % 255))
        t = round(t + step, 3)
    return done


def test_clip_covers_before_and_after_the_alert(rec):
    run(rec, 0, 10)                          # frames before the alert are buffered
    rec.request(7, 10.0)                     # alert #7 at t=10
    assert run(rec, 10.5, 13.5) == []        # not finished until 4 s after
    done = run(rec, 14.0, 14.0)
    assert len(done) == 1
    aid, path, n, fps = done[0]
    assert aid == 7 and n == 17               # t = 6.0 .. 14.0 every 0.5 s
    assert sorted(os.listdir(path))[0] == "000.jpg" and len(os.listdir(path)) == n
    with open(os.path.join(path, "000.jpg"), "rb") as f:
        assert f.read(2) == b"\xff\xd8"
    assert fps == pytest.approx(2.0)


def test_memory_stays_bounded(rec):
    run(rec, 0, 300)
    assert len(rec.buf) <= (4 + 4 + 2) / 0.5 + 2


def test_flush_writes_what_it_has_on_shutdown(rec):
    run(rec, 0, 5)
    rec.request(1, 5.0)
    done = rec.flush()
    assert len(done) == 1 and done[0][2] == 9     # t = 1.0 .. 5.0, nothing after


def test_old_clips_are_pruned(rec):
    for aid in range(1, 6):
        run(rec, aid * 20, aid * 20 + 3)
        rec.request(aid, aid * 20 + 3.0)
        run(rec, aid * 20 + 3.5, aid * 20 + 8)
    assert sorted(os.listdir(rec.clip_dir), key=int) == ["3", "4", "5"]   # keep=3


def test_store_forwards_clip_after_its_alert(tmp_config, tmp_path):
    from alert_store import AlertStore
    from clip_recorder import ClipRecorder
    st = AlertStore()
    aid = st.maybe_add({"type": "fire", "conf": .8, "box": [1, 1, 9, 9]}, frame(9), 1.0, 1, 1)
    r = ClipRecorder(before=1, after=1, clip_dir=str(tmp_path / "c"))
    run(r, 0, 1)
    r.request(aid, 1.0)
    (_, path, n, fps), = run(r, 1.5, 2.0)
    st.set_clip(aid, path, n, fps)
    row = st.db.execute("SELECT clip, clip_frames, clip_sent FROM alerts").fetchone()
    assert row == (path, n, 0)

    calls = []

    class Resp:
        def __init__(self, code):
            self.status_code = code

    class FakeRequests:
        @staticmethod
        def post(url, data=None, files=None, headers=None, timeout=None):
            calls.append((url, data, [f[0] for f in files]))
            return Resp(200)

    assert st.forward_clips("http://gs", {}, requests=FakeRequests) == (0, 1)   # alert not sent yet
    st.db.execute("UPDATE alerts SET sent=1")
    assert st.forward_clips("http://gs", {}, requests=FakeRequests) == (1, 0)
    url, data, names = calls[0]
    assert url == "http://gs/api/clip" and data["alert_id"] == aid and len(names) == n
    assert st.db.execute("SELECT clip_sent FROM alerts").fetchone()[0] == 1


def test_clip_given_up_when_station_does_not_know_the_alert(tmp_config, tmp_path):
    from alert_store import AlertStore
    st = AlertStore()
    aid = st.maybe_add({"type": "fire", "conf": .8, "box": [1, 1, 9, 9]}, frame(9), 1.0, 1, 1)
    d = tmp_path / "c"
    d.mkdir()
    (d / "000.jpg").write_bytes(b"\xff\xd8x")
    st.set_clip(aid, str(d), 1, 2.0)
    st.db.execute("UPDATE alerts SET sent=1")

    class FakeRequests:
        @staticmethod
        def post(*a, **k):
            return type("R", (), {"status_code": 404})()

    assert st.forward_clips("http://gs", {}, requests=FakeRequests) == (0, 0)
    assert st.db.execute("SELECT clip_sent FROM alerts").fetchone()[0] == 2   # never retried


def test_old_drone_database_gets_clip_columns(tmp_config):
    import sqlite3
    db = sqlite3.connect(config.DB_PATH)
    db.execute("""CREATE TABLE alerts (id INTEGER PRIMARY KEY AUTOINCREMENT,
        video_time REAL, wall_time TEXT, type TEXT, conf REAL, lat REAL, lon REAL,
        snapshot TEXT, priority INTEGER, sent INTEGER DEFAULT 0)""")
    db.commit()
    db.close()
    from alert_store import AlertStore
    cols = {r[1] for r in AlertStore().db.execute("PRAGMA table_info(alerts)")}
    assert {"clip", "clip_frames", "clip_fps", "clip_sent"} <= cols
