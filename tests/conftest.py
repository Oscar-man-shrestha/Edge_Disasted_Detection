import os
import sys

import numpy as np
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "ground_station"))

import config  # noqa: E402


@pytest.fixture
def tmp_config(tmp_path, monkeypatch):
    """Point every file the code writes at a temp dir."""
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "alerts.db"))
    monkeypatch.setattr(config, "SNAPSHOT_DIR", str(tmp_path / "snaps"))
    monkeypatch.setattr(config, "CLIP_DIR", str(tmp_path / "clips"))       # never the real data/clips
    monkeypatch.setattr(config, "FLIGHT_PATH_CSV", os.path.join(REPO, "data", "flight_path.csv"))
    return tmp_path


@pytest.fixture
def textured_world():
    """Grey random texture, bigger than a frame, so we can 'fly' over it."""
    import cv2
    rng = np.random.default_rng(0)
    w = rng.integers(0, 255, (900, 1600), dtype=np.uint8)
    w = cv2.GaussianBlur(w, (0, 0), 3)
    w = cv2.normalize(w, None, 0, 255, cv2.NORM_MINMAX)
    return cv2.cvtColor(w, cv2.COLOR_GRAY2BGR)
