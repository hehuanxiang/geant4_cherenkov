#!/usr/bin/env python3
"""
Minimal regression tests for build_dose_kernel.py.
Creates synthetic .dose and run_meta, runs build_dose_kernel, asserts:
  - sum(kernel_02) ≈ total_energy/N_primaries (tolerance)
  - fast mode: kernel_03 != kernel_02
  - grid shape matches edges
  - kernel_05 exists, shape/dtype float64, Gy formula (density=1.0), 4 Gy plots exist
  - non-default density: kernel_05 scales as 1/rho
"""

import json
import os
import subprocess
import sys
import tempfile

import numpy as np

DOSE_DTYPE = np.dtype([
    ("x", "f4"), ("y", "f4"), ("z", "f4"),
    ("dx", "f4"), ("dy", "f4"), ("dz", "f4"),
    ("energy", "f4"), ("event_id", "u4"), ("pdg", "i4"),
])
J_PER_MEV = 1.602176634e-10
GY_PLOT_NAMES = [
    "plot_05_xy_slice_center_z_Gy.png",
    "plot_06_xz_slice_center_y_Gy.png",
    "plot_07_depth_profile_Kz_Gy.png",
    "plot_08_radial_profile_Kr_Gy.png",
]


def _script_dir():
    return os.path.dirname(os.path.abspath(__file__))


def create_synthetic_dose(path_dose, path_run_meta, n_primaries=4, n_records=40):
    """Create minimal .dose and .run_meta for testing."""
    # Records: dx,dy,dz in [-2,2], energy 0.1 MeV each, event_id 0..3
    np.random.seed(42)
    n = n_records
    data = np.zeros(n, dtype=DOSE_DTYPE)
    data["x"] = np.random.uniform(-2, 2, n).astype(np.float32)
    data["y"] = np.random.uniform(-2, 2, n).astype(np.float32)
    data["z"] = np.random.uniform(-1, 1, n).astype(np.float32)
    data["dx"] = data["x"]
    data["dy"] = data["y"]
    data["dz"] = data["z"]
    data["energy"] = 0.1
    data["event_id"] = np.random.randint(0, n_primaries, n, dtype=np.uint32)
    data["pdg"] = 22
    data.tofile(path_dose)

    with open(path_run_meta, "w") as f:
        json.dump({"events": n_primaries}, f)


def run_build_dose_kernel(dose_path, run_meta_path, out_dir, n_primaries, extra_args=None):
    """Run build_dose_kernel.py with --use-dxdydz (no config). extra_args: optional list, e.g. ['--density-g-cm3', '2.0']."""
    script = os.path.join(_script_dir(), "build_dose_kernel.py")
    cmd = [
        sys.executable,
        script,
        "--dose", dose_path,
        "--output-dir", out_dir,
        "--n-primaries", str(n_primaries),
        "--use-dxdydz",
        "--chunk-size", "10",
    ]
    if extra_args:
        cmd.extend(extra_args)
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=_script_dir())
    return result.returncode == 0, result.stdout, result.stderr


def test_build_dose_kernel():
    n_primaries = 4
    n_records = 40
    total_energy = n_records * 0.1  # 4.0 MeV

    with tempfile.TemporaryDirectory() as tmp:
        dose_path = os.path.join(tmp, "test.dose")
        run_meta_path = os.path.join(tmp, "test.run_meta.json")
        out_dir = os.path.join(tmp, "out")
        os.makedirs(out_dir)

        create_synthetic_dose(dose_path, run_meta_path, n_primaries, n_records)
        ok, stdout, stderr = run_build_dose_kernel(dose_path, run_meta_path, out_dir, n_primaries)
        if not ok:
            print("STDOUT:", stdout)
            print("STDERR:", stderr)
            assert ok, f"build_dose_kernel failed"

        K = np.load(os.path.join(out_dir, "kernel_02_normalized.npy"))
        sigma = np.load(os.path.join(out_dir, "kernel_03_uncertainty.npy"))
        edges = np.load(os.path.join(out_dir, "kernel_04_voxel_edges.npz"))
        with open(os.path.join(out_dir, "kernel_stats.json")) as f:
            stats = json.load(f)

        # Assert 1: sum(kernel_02) ≈ total_energy / N_primaries
        expected_per_primary = total_energy / n_primaries
        actual_sum = float(K.sum())
        rel_err = abs(actual_sum - expected_per_primary) / max(expected_per_primary, 1e-20)
        assert rel_err < 0.01, f"sum(kernel_02)={actual_sum} vs total/N={expected_per_primary} (rel_err={rel_err})"

        # Assert 2: fast mode: kernel_03 != kernel_02
        assert not np.allclose(sigma, K), "kernel_03 should differ from kernel_02 in fast mode"

        # Assert 3: grid shape matches edges
        nx = len(edges["x_edges"]) - 1
        ny = len(edges["y_edges"]) - 1
        nz = len(edges["z_edges"]) - 1
        assert K.shape == (nx, ny, nz), f"K.shape={K.shape} vs edges ({nx},{ny},{nz})"
        assert stats["grid_shape"] == [nx, ny, nz]

        # Assert 4: kernel_05 exists, same shape as kernel_02, dtype float64
        kernel_05_path = os.path.join(out_dir, "kernel_05_dose_Gy_per_primary.npy")
        assert os.path.isfile(kernel_05_path), "kernel_05_dose_Gy_per_primary.npy must exist"
        kernel_05 = np.load(kernel_05_path)
        assert kernel_05.shape == K.shape, f"kernel_05.shape={kernel_05.shape} vs K.shape={K.shape}"
        assert kernel_05.dtype == np.float64, f"kernel_05 must be float64, got {kernel_05.dtype}"

        # Assert 5: four Gy plot files exist
        for name in GY_PLOT_NAMES:
            p = os.path.join(out_dir, name)
            assert os.path.isfile(p), f"Gy plot must exist: {name}"

        # Assert 6: Gy formula (density=1.0): dose_Gy = K * J_PER_MEV / (density * voxel_volume_cm3)
        voxel_volume_cm3 = float(stats["voxel_volume_cm3"])
        density = 1.0
        expected_Gy = K * J_PER_MEV / (density * voxel_volume_cm3)
        assert np.allclose(kernel_05, expected_Gy, rtol=1e-5), (
            "kernel_05 should match K*J_PER_MEV/(density*voxel_volume_cm3)"
        )

        # Assert 7: non-default density 1/rho scaling: run with density=2.0, kernel_05 should be half
        out_dir_rho2 = os.path.join(tmp, "out_rho2")
        os.makedirs(out_dir_rho2)
        ok2, stdout2, stderr2 = run_build_dose_kernel(
            dose_path, run_meta_path, out_dir_rho2, n_primaries,
            extra_args=["--density-g-cm3", "2.0"],
        )
        assert ok2, f"build_dose_kernel with density=2.0 failed: {stderr2}"
        kernel_05_rho2 = np.load(os.path.join(out_dir_rho2, "kernel_05_dose_Gy_per_primary.npy"))
        # kernel_05 (density=1) should be 2x kernel_05_rho2 (density=2)
        assert np.allclose(kernel_05, 2.0 * kernel_05_rho2, rtol=1e-5), (
            "kernel_05 should scale as 1/rho: density=2 -> half values"
        )


def test_density_validation_rejects_non_positive():
    """--density-g-cm3 <= 0 must raise ValueError (script exits non-zero)."""
    n_primaries = 4
    with tempfile.TemporaryDirectory() as tmp:
        dose_path = os.path.join(tmp, "test.dose")
        run_meta_path = os.path.join(tmp, "test.run_meta.json")
        out_dir = os.path.join(tmp, "out")
        os.makedirs(out_dir)
        create_synthetic_dose(dose_path, run_meta_path, n_primaries, 20)
        ok, _, stderr = run_build_dose_kernel(
            dose_path, run_meta_path, out_dir, n_primaries,
            extra_args=["--density-g-cm3", "0"],
        )
        assert not ok, "build_dose_kernel must fail for density=0"
        assert "density_g_cm3 must be positive" in stderr or "ValueError" in stderr


if __name__ == "__main__":
    test_build_dose_kernel()
    test_density_validation_rejects_non_positive()
    print("test_build_dose_kernel: OK")
