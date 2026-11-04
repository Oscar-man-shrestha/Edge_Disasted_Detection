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
