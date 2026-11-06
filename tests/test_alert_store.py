"""Drone-side alert buffer: snapshot files and timestamps."""
import os
import re

import numpy as np

FRAME = np.full((360, 640, 3), 90, np.uint8)
FIRE = {"type": "fire", "conf": 0.8, "box": [100, 100, 300, 250]}


def snapshots(store):
    return [r[0] for r in store.db.execute("SELECT snapshot FROM alerts ORDER BY id")]


def test_snapshots_do_not_clash_across_restarts(tmp_config):
    """The pipeline clock restarts at 0 on every run; a new alert must never
    overwrite the photo of an older (possibly still unsent) alert."""
    from alert_store import AlertStore
    AlertStore().maybe_add(FIRE, FRAME, 5.0, 12.97, 77.59)
    first = snapshots(AlertStore())[0]
    before = os.path.getmtime(first), os.path.getsize(first)
    AlertStore().maybe_add(FIRE, FRAME + 40, 5.0, 12.97, 77.59)     # "restart", same t
    names = snapshots(AlertStore())
    assert len(names) == 2 and names[0] != names[1]
    assert all(os.path.isfile(n) for n in names)
    assert (os.path.getmtime(first), os.path.getsize(first)) == before


def test_wall_time_carries_timezone(tmp_config):
    from alert_store import AlertStore
    st = AlertStore()
    st.maybe_add(FIRE, FRAME, 1.0, None, None)
    wall = st.db.execute("SELECT wall_time FROM alerts").fetchone()[0]
    assert re.fullmatch(r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d [+-]\d{4}", wall), wall
