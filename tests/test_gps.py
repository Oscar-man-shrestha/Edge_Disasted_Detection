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
