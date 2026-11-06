"""Tiled person detection on the full-resolution frame (longer range)."""
import numpy as np
import pytest

import config
from stage2_detector import Stage2Detector, merge_dets, tile_boxes


def test_two_tiles_cover_the_frame_and_overlap():
    tiles = tile_boxes(1280, 720, 2, overlap=0.2)
    assert len(tiles) == 2
    (a0, ay0, a1, ay1), (b0, by0, b1, by1) = tiles
    assert a0 == 0 and b1 == 1280 and ay0 == by0 == 0 and ay1 == by1 == 720
    assert b0 < a1                                   # they overlap ...
    assert a1 - b0 >= 0.2 * (a1 - a0) - 1            # ... by about 20 % of a tile
    assert tile_boxes(1280, 720, 0) == [] and tile_boxes(1280, 720, 1) == []


def det(t, c, box):
    return {"type": t, "conf": c, "box": list(map(float, box))}


def test_merge_removes_duplicates_and_keeps_separate_people():
    dets = [
        det("person", .9, (100, 100, 200, 300)),
        det("person", .7, (102, 98, 203, 305)),       # same person found again: dropped
        det("person", .6, (120, 120, 190, 200)),      # half of the same person, inside it: dropped
        det("person", .8, (400, 100, 480, 300)),      # someone else: kept
        det("fire", .5, (100, 100, 200, 300)),        # other type at the same place: kept
    ]
    got = merge_dets(dets)
    assert sorted((d["type"], d["conf"]) for d in got) == [("fire", .5), ("person", .8), ("person", .9)]


class FakeBox:
    def __init__(self, cls, conf, xyxy):
        self.cls, self.conf, self.xyxy = [cls], [conf], [np.array(xyxy, float)]


class FakeModel:
    """Finds one 'person' in whatever image it gets if it is big enough: like YOLO, small = missed."""
    def __init__(self):
        self.calls = []

    def predict(self, img, **kw):
        self.calls.append(img.shape)
        ys, xs = np.where(img[:, :, 0] > 200)            # the white "person"
        boxes = []
        if len(xs) and (ys.max() - ys.min() + 1) * 640 / max(img.shape[:2]) >= 20:   # YOLO scales the long side to 640
            boxes.append(FakeBox(0, 0.8, (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)))
        return [type("R", (), {"boxes": boxes, "names": {0: "person"}})()]


def detector():
    d = Stage2Detector.__new__(Stage2Detector)
    d.person_model, d.fire_model = FakeModel(), None
    return d


def scene():
    full = np.zeros((720, 1280, 3), np.uint8)
    full[300:324, 900:908] = 255                         # far away: 24 px tall at full resolution
    small = full[::2, ::2].copy()                        # what the pipeline normally looks at
    return full, small


def test_far_person_only_found_with_tiles(monkeypatch):
    full, small = scene()
    monkeypatch.setattr(config, "TILES", 0)
    assert detector().detect(small, full=full)[0] == []                  # 12 px at 640: missed
    monkeypatch.setattr(config, "TILES", 2)
    d = detector()
    dets, _ = d.detect(small, full=full)
    assert len(dets) == 1 and dets[0]["type"] == "person"
    x1, y1, x2, y2 = dets[0]["box"]                                     # in the small frame's pixels
    assert (x1, y1, x2, y2) == pytest.approx((450, 150, 454, 162), abs=1)
    assert len(d.person_model.calls) == 3                               # whole frame + 2 tiles


def test_without_a_full_frame_it_works_as_before(monkeypatch):
    monkeypatch.setattr(config, "TILES", 2)
    _, small = scene()
    d = detector()
    d.detect(small)
    assert len(d.person_model.calls) == 1


class FakeFire(FakeModel):
    def predict(self, img, **kw):
        r = super().predict(img, **kw)[0]
        r.names = {0: "fire"}
        return [r]


def test_small_far_fire_found_with_fire_tiling(monkeypatch):
    full, small = scene()                              # same tiny bright blob, now "a fire"
    monkeypatch.setattr(config, "TILES", 2)
    d = Stage2Detector.__new__(Stage2Detector)
    d.person_model, d.fire_model = FakeModel(), FakeFire()
    monkeypatch.setattr(config, "TILE_FIRE", False)
    types = [x["type"] for x in d.detect(small, full=full)[0]]
    assert types == ["person"]                         # fire model only saw the small frame
    monkeypatch.setattr(config, "TILE_FIRE", True)
    d.fire_model = FakeFire()
    types = sorted(x["type"] for x in d.detect(small, full=full)[0])
    assert types == ["fire", "person"]
    assert len(d.fire_model.calls) == 3                # whole frame + 2 tiles
