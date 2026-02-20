#!/usr/bin/env python3
"""Regression tests for build_cherenkov_kernel.py with v2 60B PHSP format."""

import json
import os
import subprocess
import sys
import tempfile
import numpy as np

PHSP_DTYPE = np.dtype([
    ("initX", "<f4"), ("initY", "<f4"), ("initZ", "<f4"),
    ("initDirX", "<f4"), ("initDirY", "<f4"), ("initDirZ", "<f4"),
    ("finalX", "<f4"), ("finalY", "<f4"), ("finalZ", "<f4"),
    ("finalDirX", "<f4"), ("finalDirY", "<f4"), ("finalDirZ", "<f4"),
    ("finalEnergy", "<f4"), ("event_id", "<u4"), ("track_id", "<i4"),
])

def _script_dir():
    return os.path.dirname(os.path.abspath(__file__))

def _project_root():
    return os.path.dirname(_script_dir())

def create_synthetic_v2_phsp(path_phsp, path_run_meta, path_header, n_photons=200, n_primaries=10):
    np.random.seed(42)
    data = np.zeros(n_photons, dtype=PHSP_DTYPE)
    data["initX"] = np.random.uniform(-5, 5, n_photons).astype(np.float32)
    data["initY"] = np.random.uniform(-5, 5, n_photons).astype(np.float32)
    data["initZ"] = np.random.uniform(25, 35, n_photons).astype(np.float32)
    data["initDirX"] = 0.0
    data["initDirY"] = 0.0
    data["initDirZ"] = 1.0
    data["finalX"] = data["initX"] + 0.1
    data["finalY"] = data["initY"] + 0.1
    data["finalZ"] = data["initZ"] + 1.0
    data["finalDirX"] = 0.0
    data["finalDirY"] = 0.0
    data["finalDirZ"] = 1.0
    data["finalEnergy"] = 2.0e6
    data["event_id"] = np.random.randint(0, n_primaries, n_photons, dtype=np.uint32)
    data["track_id"] = np.arange(1, n_photons + 1, dtype=np.int32)
    data.tofile(path_phsp)
    with open(path_run_meta, "w") as f:
        json.dump({"events": n_primaries, "total_photons": n_photons}, f)
    with open(path_header, "w") as f:
        f.write("format_version: 2\nbytes_per_photon: 60\n")

def run_build_cherenkov_kernel(phsp_path, config_path, out_dir, n_primaries):
    script = os.path.join(_script_dir(), "build_cherenkov_kernel.py")
    cmd = [sys.executable, script, "--phsp", phsp_path, "--config", config_path,
           "--output-dir", out_dir, "--n-primaries", str(n_primaries), "--chunk-size", "50"]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=_script_dir())
    return result.returncode == 0, result.stdout, result.stderr

def test_build_cherenkov_kernel():
    n_primaries, n_photons = 10, 200
    with tempfile.TemporaryDirectory() as tmp:
        base = os.path.join(tmp, "test")
        phsp_path = base + ".phsp"
        run_meta_path = base + ".run_meta.json"
        header_path = base + ".header"
        out_dir = os.path.join(tmp, "out")
        os.makedirs(out_dir)
        create_synthetic_v2_phsp(phsp_path, run_meta_path, header_path, n_photons, n_primaries)
        config_path = os.path.join(_project_root(), "config.json")
        if not os.path.isfile(config_path):
            raise FileNotFoundError(f"config.json not found at {config_path}")
        ok, stdout, stderr = run_build_cherenkov_kernel(phsp_path, config_path, out_dir, n_primaries)
        if not ok:
            print("STDOUT:", stdout)
            print("STDERR:", stderr)
            assert ok
        K = np.load(os.path.join(out_dir, "kernel_02_normalized.npy"))
        edges = np.load(os.path.join(out_dir, "kernel_04_voxel_edges.npz"))
        with open(os.path.join(out_dir, "kernel_stats.json")) as f:
            stats = json.load(f)
        assert K.shape == (len(edges["x_edges"]) - 1, len(edges["y_edges"]) - 1, len(edges["z_edges"]) - 1)
        assert stats["photons_read"] == n_photons
        assert stats["n_primaries"] == n_primaries

if __name__ == "__main__":
    test_build_cherenkov_kernel()
    print("test_build_cherenkov_kernel: OK")
