#!/usr/bin/env python3
"""
Test v2 PHSP read path in analyze_cherenkov_fast.load_and_process_data.
"""

import os
import sys
import tempfile

import numpy as np

PHSP_DTYPE = np.dtype([
    ("initX", "<f4"), ("initY", "<f4"), ("initZ", "<f4"),
    ("initDirX", "<f4"), ("initDirY", "<f4"), ("initDirZ", "<f4"),
    ("finalX", "<f4"), ("finalY", "<f4"), ("finalZ", "<f4"),
    ("finalDirX", "<f4"), ("finalDirY", "<f4"), ("finalDirZ", "<f4"),
    ("finalEnergy", "<f4"),
    ("event_id", "<u4"),
    ("track_id", "<i4"),
])


def _script_dir():
    return os.path.dirname(os.path.abspath(__file__))


def _project_root():
    return os.path.dirname(_script_dir())


def test_analyze_cherenkov_fast_v2_load():
    """Create synthetic v2 phsp, patch BINARY_FILE, call load_and_process_data, assert event_id/track_id."""
    np.random.seed(44)
    n = 100
    data = np.zeros(n, dtype=PHSP_DTYPE)
    data["initX"] = np.random.uniform(-2, 2, n).astype(np.float32)
    data["initY"] = np.random.uniform(-2, 2, n).astype(np.float32)
    data["initZ"] = np.random.uniform(25, 35, n).astype(np.float32)
    data["initDirX"] = 0.0
    data["initDirY"] = 0.0
    data["initDirZ"] = 1.0
    data["finalX"] = data["initX"]
    data["finalY"] = data["initY"]
    data["finalZ"] = data["initZ"] + 1.0
    data["finalDirX"] = 0.0
    data["finalDirY"] = 0.0
    data["finalDirZ"] = 1.0
    data["finalEnergy"] = 2e6
    data["event_id"] = np.arange(n, dtype=np.uint32) % 10
    data["track_id"] = np.arange(1, n + 1, dtype=np.int32)

    with tempfile.TemporaryDirectory() as tmp:
        phsp_path = os.path.join(tmp, "test.phsp")
        data.tofile(phsp_path)

        sys.path.insert(0, _project_root())
        import analyze_cherenkov_fast as acf
        acf.BINARY_FILE = phsp_path

        result = acf.load_and_process_data()
        assert "event_id" in result
        assert "track_id" in result
        assert result["event_id"].min() >= 0
        assert result["event_id"].max() < 10
        assert result["track_id"].min() >= 1
        assert result["track_id"].max() <= n


if __name__ == "__main__":
    test_analyze_cherenkov_fast_v2_load()
    print("test_analyze_cherenkov_fast: OK")
