import math
import pytest
from gps_sim import GPSSim
from gps_source import make_gps


def test_sim_start_end_and_hold(tmp_config):
    g = GPSSim()
    assert g.position(0) == g.pts[0]
    assert g.position(1e9) == g.pts[-1]
    lat, lon = g.position(10)
    assert abs(lat - g.pts[0][0]) * 111320 == pytest.approx(50, abs=0.5)   # 5 m/s * 10 s


def test_make_gps_sim(tmp_config):
    assert isinstance(make_gps("sim"), GPSSim)


def test_make_gps_unknown():
    with pytest.raises(ValueError):
        make_gps("nope")


def test_sim_status_has_course_and_speed(tmp_config):
    st = GPSSim().status(10)
    assert st["mode"] == "sim"
    assert st["fix"] is True
    assert st["course_deg"] == pytest.approx(0, abs=1)      # first leg heads north
    assert st["speed_mps"] == 5.0
    assert st["lat"] is not None and st["lon"] is not None
