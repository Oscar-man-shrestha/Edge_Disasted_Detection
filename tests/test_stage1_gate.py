import numpy as np
import pytest
import config
from stage1_gate import Stage1Gate


def pan(world, n, step):
    return [world[100:460, 100 + i * step:740 + i * step].copy() for i in range(n)]


def test_fire_colour_triggers_after_streak():
    g = Stage1Gate(motion_compensation=False)
    f = np.zeros((360, 640, 3), np.uint8)
    f[100:200, 100:300] = (0, 140, 255)            # orange, BGR
    rs = [g.check(f) for _ in range(config.CONSECUTIVE_FLAGS_NEEDED)]
    assert all(r["flagged"] for r in rs)
    assert [r["trigger"] for r in rs] == [False] * (config.CONSECUTIVE_FLAGS_NEEDED - 1) + [True]


def test_calm_static_scene_never_triggers(textured_world):
    g = Stage1Gate()
    f = textured_world[:360, :640]
    assert not any(g.check(f.copy())["trigger"] for _ in range(10))


def test_panning_triggers_without_compensation(textured_world):
    g = Stage1Gate(motion_compensation=False)
    assert any(g.check(f)["trigger"] for f in pan(textured_world, 8, 12))


def test_panning_ignored_with_compensation(textured_world):
    g = Stage1Gate(motion_compensation=True)
    rs = [g.check(f) for f in pan(textured_world, 8, 12)]
    assert not any(r["trigger"] for r in rs)
    assert all(r["aligned"] for r in rs[1:])
    assert max(r["diff_frac"] for r in rs[1:]) < 0.02


def test_real_change_still_detected_with_compensation(textured_world):
    g = Stage1Gate(motion_compensation=True)
    frames = pan(textured_world, 8, 12)
    for i, f in enumerate(frames[3:], 3):          # big object jumps around after frame 3
        x = 40 if i % 2 else 340
        f[60:320, x:x + 260] = 255
    rs = [g.check(f) for f in frames]
    assert any(r["trigger"] for r in rs)


def test_featureless_frame_falls_back_without_crash():
    g = Stage1Gate(motion_compensation=True)
    f = np.full((360, 640, 3), 90, np.uint8)
    r1, r2 = g.check(f), g.check(f)
    assert r2["aligned"] is False and r2["diff_frac"] == 0.0


def test_motion_sensitivity_independent_of_sample_rate(monkeypatch):
    """A square moving at constant speed must flag the same at 2 and at 4 frames/s:
    the gate compares with the frame ~0.5 s ago, not just the previous one."""
    import config
    from stage1_gate import Stage1Gate
    monkeypatch.setattr(config, "FIRE_PIXEL_FRACTION", 2.0)          # motion only

    def frames(step_px):
        for k in range(12):
            f = np.full((360, 640, 3), 60, np.uint8)
            x = 40 + int(k * step_px)
            f[100:300, x:x + 200] = 220
            yield f

    def diffs(interval, step_px):
        monkeypatch.setattr(config, "SAMPLE_INTERVAL_SEC", interval)
        g = Stage1Gate(motion_compensation=False)
        return [g.check(f)["diff_frac"] for f in frames(step_px)][4:]

    slow = diffs(0.5, 20)          # 40 px/s seen at 2 fps (square stays inside the frame)
    fast = diffs(0.25, 10)         # the same 40 px/s seen at 4 fps
    assert min(fast) == pytest.approx(min(slow), rel=0.05)
