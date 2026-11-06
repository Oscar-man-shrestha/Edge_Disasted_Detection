from stage2_detector import Stage2Scheduler

HIT, MISS = [{"type": "fire"}], []


def run(s, triggers, result):
    out = []
    for t in triggers:
        r = s.should_run(t)
        out.append(r)
        if r:
            s.update(result)
    return out


def test_runs_every_frame_until_confirmed():
    assert run(Stage2Scheduler(3), [True] * 4, MISS) == [True] * 4


def test_every_nth_while_confirmed():
    s = Stage2Scheduler(3)
    assert run(s, [True] * 7, HIT) == [True, False, False, True, False, False, True]
    assert s.skipped == 4


def test_trigger_drop_resets():
    s = Stage2Scheduler(3)
    run(s, [True], HIT)
    assert s.should_run(False) is False
    assert s.should_run(True) is True


def test_miss_while_confirmed_goes_back_to_every_frame():
    s = Stage2Scheduler(2)
    run(s, [True], HIT)
    assert s.should_run(True) is False
    assert s.should_run(True) is True
    s.update(MISS)
    assert s.should_run(True) is True


def test_n_equals_one_is_old_behaviour():
    assert run(Stage2Scheduler(1), [True] * 5, HIT) == [True] * 5


def test_scan_runs_stage2_every_n_seconds_without_any_trigger():
    """Still or far targets never trigger the motion gate: a periodic scan still looks."""
    s = Stage2Scheduler(3, scan_every=2.0)
    ran = [t for t in [x * 0.25 for x in range(0, 41)] if s.should_run(False, t)]   # 10 s, no motion
    assert ran == [0.0, 2.0, 4.0, 6.0, 8.0, 10.0]
    assert s.scans == 6


def test_scan_does_not_add_runs_while_stage2_is_busy_anyway():
    s = Stage2Scheduler(1, scan_every=2.0)
    runs = [s.should_run(True, x * 0.25) for x in range(0, 9)]                        # triggered: runs
    assert all(runs) and s.scans == 0


def test_scan_off_by_default_keeps_old_behaviour():
    s = Stage2Scheduler(3, scan_every=0)
    assert not any(s.should_run(False, x * 0.5) for x in range(100))
