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


SURVEY = "data/survey_path.csv"


def test_loop_keeps_flying_and_closes_without_a_jump(tmp_config):
    """Patrol mode: never parks at the end; comes back to the start along a real leg."""
    g = GPSSim(path_csv=SURVEY, loop=True)
    lap = g.total / g.speed
    assert g.position(0) == pytest.approx(g.pts[0])
    assert g.position(lap) == pytest.approx(g.pts[0], abs=1e-9)          # one full lap = home
    assert g.position(lap + 10) == pytest.approx(g.position(10))         # and it repeats
    st = g.status(lap * 3 + 7)
    assert st["speed_mps"] == g.speed                                     # still moving after hours
    prev = g.position(0)
    for k in range(1, int(lap * 2)):                                      # 1 s steps over two laps
        cur = g.position(k)
        step = GPSSim._dist(prev, cur)
        assert step <= g.speed + 1e-6, "teleport at t=%d (%.1f m)" % (k, step)
        prev = cur


def test_loop_course_follows_the_lanes(tmp_config):
    g = GPSSim(path_csv=SURVEY, loop=True)
    assert g.status(5)["course_deg"] == pytest.approx(0, abs=1)          # first lane: north
    lane = GPSSim._dist(g.pts[0], g.pts[1]) / g.speed
    turn = GPSSim._dist(g.pts[1], g.pts[2]) / g.speed
    assert g.status(lane + turn / 2)["course_deg"] == pytest.approx(90, abs=1)        # step east
    assert g.status(lane + turn + 5)["course_deg"] == pytest.approx(180, abs=1)       # back south


def test_default_still_flies_once_and_holds(tmp_config):
    g = GPSSim()
    assert g.status(1e6)["speed_mps"] == 0.0


# ---- simulator remote (manual steering from the ground station)
def man(seq, heading, speed):
    return {"id": "s:%d" % seq, "mode": "manual", "heading": heading, "speed": speed}


def test_manual_steering_moves_from_where_the_drone_is(tmp_config):
    g = GPSSim(path_csv=SURVEY, loop=True)
    here = g.position(20)                                        # on the first lane, going north
    g.control(man(1, 90, 4.0), 20)                               # take over: east at 4 m/s
    lat, lon = g.position(30)                                    # 10 s later
    assert lat == pytest.approx(here[0], abs=1e-7)
    assert GPSSim._dist(here, (lat, lon)) == pytest.approx(40, abs=0.5)
    assert lon > here[1]
    st = g.status(30)
    assert st["control"] == "manual" and st["course_deg"] == 90 and st["speed_mps"] == 4.0
    g.control(man(2, 0, 0.0), 30)                                # stop: hover in place
    assert g.position(60) == pytest.approx((lat, lon))
    assert g.status(60)["speed_mps"] == 0.0


def test_same_command_twice_is_applied_once(tmp_config):
    g = GPSSim(path_csv=SURVEY, loop=True)
    g.control(man(1, 90, 5.0), 0)
    g.position(10)
    g.control(man(1, 90, 5.0), 10)                               # repeated in every telemetry reply
    p = g.position(20)
    assert GPSSim._dist(g.pts[0], p) == pytest.approx(100, abs=0.5)


def test_resume_flies_back_to_the_route_then_patrols_without_a_jump(tmp_config):
    g = GPSSim(path_csv=SURVEY, loop=True)
    g.control(man(1, 270, 5.0), 0)                               # 100 m west, off the route
    off = g.position(20)
    g.control({"id": "s:2", "mode": "auto"}, 20)
    assert g.status(20)["control"] == "return"
    prev, t = off, 20.0
    while g.status(t)["control"] == "return" and t < 200:        # no step faster than the speed
        t += 0.5
        cur = g.position(t)
        assert GPSSim._dist(prev, cur) <= 5.0 * 0.5 + 1e-6
        prev = cur
    assert g.status(t)["control"] == "auto"
    for _ in range(40):                                          # and patrol continues smoothly
        t += 0.5
        cur = g.position(t)
        assert GPSSim._dist(prev, cur) <= 5.0 * 0.5 + 1e-6
        prev = cur


def test_bad_commands_are_ignored_and_clamped(tmp_config):
    g = GPSSim(path_csv=SURVEY, loop=True)
    g.control({"id": "s:1", "mode": "fly-me-to-the-moon"}, 0)
    assert g.status(0)["control"] == "auto"
    g.control(man(2, 450, 99), 0)                                 # heading wraps, speed capped
    st = g.status(0)
    assert st["course_deg"] == 90 and st["speed_mps"] == 15.0
