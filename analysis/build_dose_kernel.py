#!/usr/bin/env python3
"""
Build 3D dose kernel from Geant4 binary .dose. Default: world (x,y,z) + config bounds/center
to match Cherenkov kernel (same grid and center for direct comparison). Use --use-dxdydz for
K_dose(dx,dy,dz) relative to primary vertex.

Outputs: kernel_01_energy_sum.npy, kernel_02_normalized.npy, kernel_03_uncertainty.npy,
kernel_04_voxel_edges.npz, kernel_stats.json/txt, and PNG plots in dose_kernel_output/.

Usage:
  python build_dose_kernel.py                    # (x,y,z) + config, same as Cherenkov
  python build_dose_kernel.py --use-dxdydz       # (dx,dy,dz) relative to primary
  python build_dose_kernel.py --n-primaries N
  python build_dose_kernel.py --uncertainty-mode event
"""

import argparse
import json
import os
import sys
from datetime import datetime
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# -----------------------------------------------------------------------------
# Dose file format: 36 B/record, 9 fields (see .dose.header)
# -----------------------------------------------------------------------------
BYTES_PER_RECORD = 36
DOSE_DTYPE = np.dtype([
    ("x", "f4"), ("y", "f4"), ("z", "f4"),
    ("dx", "f4"), ("dy", "f4"), ("dz", "f4"),
    ("energy", "f4"), ("event_id", "u4"), ("pdg", "i4"),
])
VOXEL_SIZE_MIN_CM = 0.3
VOXEL_SIZE_MAX_CM = 0.8
TARGET_BINS_LARGEST_DIM = 100
DEFAULT_CHUNK_RECORDS = 1_000_000
# std_e for event-level uncertainty: ddof=1 (sample std), fixed in plan
EVENT_LEVEL_STD_DDOF = 1


def _script_dir():
    return os.path.dirname(os.path.abspath(__file__))


def _project_root():
    return os.path.dirname(_script_dir())


def parse_args():
    """Parse command-line arguments; defaults from project layout."""
    root = _script_dir()
    proot = _project_root()
    p = argparse.ArgumentParser(description="Build 3D dose kernel from binary .dose (dx,dy,dz or x,y,z).")
    p.add_argument("--dose", default=os.path.join(proot, "output", "cherenkov_photons_full_with_dose.dose"),
                   help="Path to .dose binary file")
    p.add_argument("--config", default=os.path.join(proot, "config.json"),
                   help="Path to config.json (required by default for bounds/center, same as Cherenkov)")
    p.add_argument("--output-dir", default=os.path.join(proot, "dose_kernel_output"),
                   help="Output directory for kernel arrays and plots")
    p.add_argument("--n-primaries", type=int, default=None,
                   help="Number of primary particles (required if not in run_meta)")
    p.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_RECORDS,
                   help=f"Records per read chunk (default {DEFAULT_CHUNK_RECORDS})")
    # Default: world (x,y,z) + config bounds/center to match Cherenkov; --use-dxdydz for relative kernel.
    p.add_argument("--use-dxdydz", action="store_true",
                   help="Bin by (dx,dy,dz) relative to primary; default is (x,y,z) to match Cherenkov")
    p.add_argument("--xy-range", nargs=2, type=float, default=None, metavar=("MIN", "MAX"),
                   help="Override x,y bounds (same as Cherenkov, e.g. -10 10)")
    p.add_argument("--uncertainty-mode", choices=("fast", "event"), default="fast",
                   help="fast: approximate sigma from sum_w2; event: event-level std (ddof=1)")
    return p.parse_args()


def path_run_meta(dose_path):
    """Same directory, same basename, .run_meta.json."""
    base = os.path.splitext(dose_path)[0]
    return base + ".run_meta.json"


def path_header(dose_path):
    """Same directory, same basename, .dose.header."""
    base = os.path.splitext(dose_path)[0]
    return base + ".dose.header"


def load_run_meta(dose_path):
    """Load run_meta.json if present. Returns dict or None."""
    path = path_run_meta(dose_path)
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_config(config_path):
    """Load config.json and return geometry (water_size_xyz_cm, water_position_cm)."""
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    geo = cfg.get("geometry", {})
    water_size = geo.get("water_size_xyz_cm")
    water_pos = geo.get("water_position_cm")
    if water_size is None or water_pos is None:
        raise ValueError("config must contain geometry.water_size_xyz_cm and geometry.water_position_cm")
    return water_size, water_pos


def get_water_bounds(water_size_xyz_cm, water_position_cm, xy_range=None):
    """World-coordinate bounds (x,y,z) and center; used when --use-xyz."""
    sx, sy, sz = water_size_xyz_cm
    cx, cy, cz = water_position_cm
    if xy_range is not None:
        xy_min, xy_max = xy_range
        x_min, x_max = xy_min, xy_max
        y_min, y_max = xy_min, xy_max
    else:
        x_min = cx - sx / 2
        x_max = cx + sx / 2
        y_min = cy - sy / 2
        y_max = cy + sy / 2
    z_min = cz - sz / 2
    z_max = cz + sz / 2
    return (x_min, x_max, y_min, y_max, z_min, z_max), (cx, cy, cz)


def get_voxel_edges(bounds):
    """From (x_min,x_max, y_min,y_max, z_min,z_max) build edges; same logic as Cherenkov."""
    x_min, x_max, y_min, y_max, z_min, z_max = bounds
    sx = x_max - x_min
    sy = y_max - y_min
    sz = z_max - z_min
    L_max = max(sx, sy, sz)
    dv = L_max / TARGET_BINS_LARGEST_DIM
    dv = np.clip(dv, VOXEL_SIZE_MIN_CM, VOXEL_SIZE_MAX_CM)
    n_x = max(1, int(round(sx / dv)))
    n_y = max(1, int(round(sy / dv)))
    n_z = max(1, int(round(sz / dv)))
    x_edges = np.linspace(x_min, x_max, n_x + 1)
    y_edges = np.linspace(y_min, y_max, n_y + 1)
    z_edges = np.linspace(z_min, z_max, n_z + 1)
    return (x_edges, y_edges, z_edges), float(dv)


def _validate_n_primaries(n):
    n = int(n)
    if n <= 0:
        raise ValueError(f"N_primaries must be positive, got {n}")
    return n


def get_n_primaries(run_meta, config_path, header_path, argparse_n_primaries):
    """Same priority as Cherenkov: run_meta['events'] -> header -> config -> argparse."""
    if run_meta is not None and "events" in run_meta:
        return _validate_n_primaries(run_meta["events"])
    if header_path and os.path.isfile(header_path):
        with open(header_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                for sep in (":", "="):
                    if sep in line:
                        k, v = line.split(sep, 1)
                        k, v = k.strip().lower(), v.strip()
                        if "primary" in k or k == "n_primaries" or k == "events":
                            try:
                                return _validate_n_primaries(float(v))
                            except ValueError:
                                pass
                        break
    if config_path and os.path.isfile(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        sim = cfg.get("simulation", {})
        for key in ("n_primaries", "num_primaries", "events", "N_primaries"):
            if key in sim:
                return _validate_n_primaries(sim[key])
    if argparse_n_primaries is not None:
        return _validate_n_primaries(argparse_n_primaries)
    raise ValueError("N_primaries not found. Provide run_meta (with 'events'), config, or --n-primaries")


def count_unique_events_chunked(dose_path, chunk_size):
    """Chunked read, count unique event_id (for N_events). Used when bounds come from config (--use-xyz)."""
    file_size = os.path.getsize(dose_path)
    n_total = file_size // BYTES_PER_RECORD
    event_ids = set()
    total_read = 0
    with open(dose_path, "rb") as f:
        while True:
            raw = f.read(chunk_size * BYTES_PER_RECORD)
            if not raw:
                break
            n_read = len(raw) // BYTES_PER_RECORD
            if n_read == 0:
                break
            data = np.frombuffer(raw, dtype=DOSE_DTYPE, count=n_read)
            event_ids.update(np.unique(data["event_id"]))
            total_read += n_read
            if total_read >= n_total:
                break
    return len(event_ids)


def scan_dose_bounds_chunked(dose_path, use_xyz, chunk_size, margin_frac=0.01):
    """
    One pass: chunked read, running min/max for (dx,dy,dz) or (x,y,z). No full array in memory.
    Returns (x_min, x_max, y_min, y_max, z_min, z_max), total_records, and unique event_id count (N_events).
    margin_frac: expand range by this fraction on each side to avoid edge clipping.
    """
    file_size = os.path.getsize(dose_path)
    if file_size % BYTES_PER_RECORD != 0:
        raise ValueError(f"Dose file size {file_size} is not divisible by {BYTES_PER_RECORD}")
    n_total = file_size // BYTES_PER_RECORD
    cols = ("x", "y", "z") if use_xyz else ("dx", "dy", "dz")
    x_min = y_min = z_min = np.inf
    x_max = y_max = z_max = -np.inf
    event_ids = set()
    total_read = 0
    with open(dose_path, "rb") as f:
        while True:
            raw = f.read(chunk_size * BYTES_PER_RECORD)
            if not raw:
                break
            n_read = len(raw) // BYTES_PER_RECORD
            if n_read == 0:
                break
            data = np.frombuffer(raw, dtype=DOSE_DTYPE, count=n_read)
            x, y, z = data[cols[0]], data[cols[1]], data[cols[2]]
            x_min, x_max = min(x_min, float(np.min(x))), max(x_max, float(np.max(x)))
            y_min, y_max = min(y_min, float(np.min(y))), max(y_max, float(np.max(y)))
            z_min, z_max = min(z_min, float(np.min(z))), max(z_max, float(np.max(z)))
            event_ids.update(np.unique(data["event_id"]))
            total_read += n_read
            if total_read % (chunk_size * 20) == 0 or total_read >= n_total:
                print(f"  Bounds scan: {total_read:,} / {n_total:,} records ...", end="\r")
    print()
    if total_read == 0:
        raise ValueError("Dose file is empty")
    if x_max <= x_min:
        x_max = x_min + 0.1
    if y_max <= y_min:
        y_max = y_min + 0.1
    if z_max <= z_min:
        z_max = z_min + 0.1
    dx_span = (x_max - x_min) * margin_frac
    dy_span = (y_max - y_min) * margin_frac
    dz_span = (z_max - z_min) * margin_frac
    x_min -= dx_span
    x_max += dx_span
    y_min -= dy_span
    y_max += dy_span
    z_min -= dz_span
    z_max += dz_span
    bounds = (float(x_min), float(x_max), float(y_min), float(y_max), float(z_min), float(z_max))
    return bounds, total_read, len(event_ids)


def build_dose_histogram_chunked(dose_path, edges, chunk_size, use_xyz):
    """
    Chunked read; weight by energy and energy**2; accumulate sum_w and sum_w2 (float64).
    Returns sum_w, sum_w2, total_energy_in_grid, total_energy_outside, total_records.
    """
    x_edges, y_edges, z_edges = edges
    bins = (x_edges, y_edges, z_edges)
    shape = (len(x_edges) - 1, len(y_edges) - 1, len(z_edges) - 1)
    sum_w = np.zeros(shape, dtype=np.float64)
    sum_w2 = np.zeros(shape, dtype=np.float64)
    cols = ("x", "y", "z") if use_xyz else ("dx", "dy", "dz")
    file_size = os.path.getsize(dose_path)
    n_total = file_size // BYTES_PER_RECORD
    total_read = 0
    total_energy_all = 0.0
    with open(dose_path, "rb") as f:
        while True:
            raw = f.read(chunk_size * BYTES_PER_RECORD)
            if not raw:
                break
            n_read = len(raw) // BYTES_PER_RECORD
            if n_read == 0:
                break
            data = np.frombuffer(raw, dtype=DOSE_DTYPE, count=n_read)
            xyz = np.column_stack([data[cols[0]], data[cols[1]], data[cols[2]]])
            w = data["energy"].astype(np.float64)
            H1, _ = np.histogramdd(xyz, bins=bins, weights=w)
            H2, _ = np.histogramdd(xyz, bins=bins, weights=w * w)
            sum_w += H1
            sum_w2 += H2
            total_read += n_read
            total_energy_all += np.sum(w)
            print(f"  Processed {total_read:,} / {n_total:,} records ...", end="\r")
    print()
    energy_in_grid = float(np.sum(sum_w))
    energy_outside = total_energy_all - energy_in_grid
    return sum_w, sum_w2, energy_in_grid, energy_outside, total_read


def compute_kernel_fast(sum_w, sum_w2, n_primaries):
    """K = sum_w / N_primaries; sigma_approx = sqrt(sum_w2) / N_primaries (approximate, not event-level)."""
    K = sum_w / n_primaries
    sigma = np.sqrt(np.maximum(sum_w2, 0.0)) / n_primaries
    return K, sigma


def build_event_level_uncertainty(dose_path, edges, chunk_size, use_xyz, n_primaries):
    """
    Stream by event_id (assume file sorted by event_id); per-event histogram -> E_e;
    vectorized per-voxel Welford (count, mean, M2); then sigma = std_e/sqrt(n) with ddof=1.
    Returns sigma_event (3D), n_events_used.
    """
    x_edges, y_edges, z_edges = edges
    bins = (x_edges, y_edges, z_edges)
    shape = (len(x_edges) - 1, len(y_edges) - 1, len(z_edges) - 1)
    cols = ("x", "y", "z") if use_xyz else ("dx", "dy", "dz")
    # Per-voxel Welford state (float64); n_ev scalar (all voxels get one sample per event)
    n_ev = 0
    mean_e = np.zeros(shape, dtype=np.float64)
    M2_e = np.zeros(shape, dtype=np.float64)
    current_event_id = None
    event_xyz_list = []
    event_w_list = []
    file_size = os.path.getsize(dose_path)
    n_total = file_size // BYTES_PER_RECORD
    total_read = 0

    def flush_event(eid, xyz, w):
        nonlocal n_ev
        if len(xyz) == 0:
            return
        xyz = np.asarray(xyz, dtype=np.float64)
        w = np.asarray(w, dtype=np.float64)
        H, _ = np.histogramdd(xyz, bins=bins, weights=w)
        n_ev += 1
        delta = H - mean_e
        mean_e[:] = mean_e + delta / n_ev
        M2_e[:] = M2_e + delta * (H - mean_e)

    with open(dose_path, "rb") as f:
        while True:
            raw = f.read(chunk_size * BYTES_PER_RECORD)
            if not raw:
                break
            n_read = len(raw) // BYTES_PER_RECORD
            if n_read == 0:
                break
            data = np.frombuffer(raw, dtype=DOSE_DTYPE, count=n_read)
            for i in range(n_read):
                eid = data["event_id"][i]
                if current_event_id is not None and eid != current_event_id:
                    flush_event(current_event_id, event_xyz_list, event_w_list)
                    event_xyz_list = []
                    event_w_list = []
                current_event_id = eid
                event_xyz_list.append([data[cols[0]][i], data[cols[1]][i], data[cols[2]][i]])
                event_w_list.append(data["energy"][i])
            total_read += n_read
            if total_read % (chunk_size * 50) == 0 or total_read >= n_total:
                print(f"  Event-level pass: {total_read:,} / {n_total:,} records ...", end="\r")
        if current_event_id is not None:
            flush_event(current_event_id, event_xyz_list, event_w_list)
    print()
    n_events_used = n_ev
    # std with ddof=1: sqrt(M2 / (n-1)); sigma of mean = std / sqrt(n)
    with np.errstate(divide="ignore", invalid="ignore"):
        variance = np.where(n_ev > 1, M2_e / (n_ev - 1), 0.0)
        std_e = np.sqrt(np.maximum(variance, 0.0))
        sigma_K = np.where(n_ev > 0, std_e / np.sqrt(n_ev), 0.0)
    return sigma_K, n_events_used


def save_arrays(out_dir, energy_sum, K, sigma, edges, uncertainty_approximate=False):
    """Save kernel_01_energy_sum, kernel_02_normalized, kernel_03_uncertainty, kernel_04_voxel_edges."""
    np.save(os.path.join(out_dir, "kernel_01_energy_sum.npy"), energy_sum)
    np.save(os.path.join(out_dir, "kernel_02_normalized.npy"), K)
    np.save(os.path.join(out_dir, "kernel_03_uncertainty.npy"), sigma)
    x_edges, y_edges, z_edges = edges
    np.savez(
        os.path.join(out_dir, "kernel_04_voxel_edges.npz"),
        x_edges=x_edges, y_edges=y_edges, z_edges=z_edges,
    )
    if uncertainty_approximate:
        # Write a small sidecar so users know kernel_03 is approximate
        with open(os.path.join(out_dir, "kernel_03_uncertainty_approximate.txt"), "w") as f:
            f.write("kernel_03_uncertainty.npy was computed with fast (approximate) mode: sigma = sqrt(sum_w2)/N_primaries. It does not account for within-event correlation. Use --uncertainty-mode event for event-level uncertainty.\n")


def voxel_centers(edges):
    return [(edges[i][:-1] + edges[i][1:]) / 2 for i in range(3)]


def plot_slices_and_profiles(out_dir, K, edges, grid_center, coord_labels, dv):
    """Four plots: XY slice, XZ slice, depth profile, radial profile; labels in MeV/primary/voxel.
    For (dx,dy,dz), grid_center should be (0,0,0) = primary vertex; for x,y,z use water center."""
    x_edges, y_edges, z_edges = edges
    cx, cy, cz = grid_center
    x_c, y_c, z_c = voxel_centers(edges)
    nx, ny, nz = K.shape
    k_center_z = np.clip(np.searchsorted(z_edges, cz, side="right") - 1, 0, nz - 1)
    j_center_y = np.clip(np.searchsorted(y_edges, cy, side="right") - 1, 0, ny - 1)
    xl, yl, zl = coord_labels
    center_note = " (primary vertex)" if (cx == 0 and cy == 0 and cz == 0) else ""

    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.pcolormesh(x_edges, y_edges, K[:, :, k_center_z].T, shading="auto", cmap="viridis")
    ax.set_xlabel(f"{xl} (cm)")
    ax.set_ylabel(f"{yl} (cm)")
    ax.set_title(f"K at {zl} = {cz:.1f} cm{center_note}")
    ax.set_aspect("equal")
    plt.colorbar(im, ax=ax, label="MeV/primary/voxel")
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "plot_01_xy_slice_center_z.png"), dpi=150, bbox_inches="tight")
    plt.close()

    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.pcolormesh(x_edges, z_edges, K[:, j_center_y, :].T, shading="auto", cmap="viridis")
    ax.set_xlabel(f"{xl} (cm)")
    ax.set_ylabel(f"{zl} (cm)")
    ax.set_title(f"K at {yl} = {cy:.1f} cm{center_note}")
    plt.colorbar(im, ax=ax, label="MeV/primary/voxel")
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "plot_02_xz_slice_center_y.png"), dpi=150, bbox_inches="tight")
    plt.close()

    Kz = np.sum(K, axis=(0, 1))
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(z_c, Kz, "b-", label="K(z)")
    ax.set_xlabel(f"{zl} (cm)")
    ax.set_ylabel(r"$\sum_{x,y} K$ (MeV/primary)")
    ax.set_title("Depth profile: K integrated over x,y")
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "plot_03_depth_profile_Kz.png"), dpi=150, bbox_inches="tight")
    plt.close()

    xx, yy, zz = np.meshgrid(x_c, y_c, z_c, indexing="ij")
    r = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    r_flat = r.ravel()
    K_flat = K.ravel()
    r_max = np.max(r)
    r_edges = np.linspace(0, r_max + 1e-9, 51)
    Kr, _ = np.histogram(r_flat, bins=r_edges, weights=K_flat)
    r_centers = (r_edges[:-1] + r_edges[1:]) / 2
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(r_centers, Kr, "b-", label="K(r)")
    ax.set_xlabel("r (cm)")
    ax.set_ylabel("K(r) (MeV/primary per radial bin)")
    ax.set_title(f"Radial profile, r = sqrt(({xl}-cx)^2+({yl}-cy)^2), center=({cx:.0f},{cy:.0f})")
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "plot_04_radial_profile_Kr.png"), dpi=150, bbox_inches="tight")
    plt.close()


def save_kernel_stats(
    out_dir,
    sum_w,
    K,
    sigma,
    edges,
    bounds,
    dv,
    n_primaries,
    n_events,
    total_energy_MeV,
    energy_in_grid,
    energy_outside,
    energy_outside_clamped,
    uncertainty_mode,
    uncertainty_approximate,
    sigma_definition,
    n_events_vs_n_primaries_warning,
    dose_path,
    config_path,
    use_xyz,
    xy_range,
):
    """kernel_stats.json and kernel_stats.txt; units MeV, MeV/primary/voxel; voxel volume for Gy conversion."""
    x_edges, y_edges, z_edges = edges
    nx, ny, nz = len(x_edges) - 1, len(y_edges) - 1, len(z_edges) - 1
    voxel_volume_cm3 = dv * dv * dv
    total_per_primary = total_energy_MeV / n_primaries if n_primaries else 0.0

    stats = {
        "units": "MeV/primary/voxel (not Gy; convert using voxel mass = density_g_cm3 * voxel_volume_cm3)",
        "total_energy_MeV": float(total_energy_MeV),
        "total_energy_per_primary_MeV": round(total_per_primary, 6),
        "energy_in_voxel_grid_MeV": float(energy_in_grid),
        "energy_outside_grid_MeV": float(energy_outside),
        "energy_outside_clamped": bool(energy_outside_clamped),
        "n_primaries": n_primaries,
        "n_events": n_events,
        "n_events_vs_n_primaries_warning": n_events_vs_n_primaries_warning,
        "bounds_cm": {
            "x_min": bounds[0], "x_max": bounds[1],
            "y_min": bounds[2], "y_max": bounds[3],
            "z_min": bounds[4], "z_max": bounds[5],
        },
        "grid_shape": [nx, ny, nz],
        "voxel_edges_summary": {
            "x": {"min": float(x_edges[0]), "max": float(x_edges[-1]), "n_bins": nx},
            "y": {"min": float(y_edges[0]), "max": float(y_edges[-1]), "n_bins": ny},
            "z": {"min": float(z_edges[0]), "max": float(z_edges[-1]), "n_bins": nz},
        },
        "voxel_size_nominal_cm": dv,
        "voxel_volume_cm3": voxel_volume_cm3,
        "density_for_Gy_conversion": "user: mass_g = density_g_cm3 * voxel_volume_cm3; dose_Gy = energy_MeV * 1.602e-10 / mass_kg",
        "kernel_stats": {
            "max": float(np.nanmax(K)),
            "mean_nonzero": float(np.nanmean(K[K > 0])) if np.any(K > 0) else 0.0,
            "total_sum_MeV_per_primary": float(K.sum()),
        },
        "uncertainty_mode": uncertainty_mode,
        "uncertainty_approximate": uncertainty_approximate,
        "sigma_definition": sigma_definition,
        "run_info": {
            "dose_path": dose_path,
            "config_path": config_path,
            "use_xyz": use_xyz,
            "xy_range": list(xy_range) if xy_range is not None else None,
            "timestamp": datetime.now().isoformat(),
        },
    }

    json_path = os.path.join(out_dir, "kernel_stats.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)

    txt_path = os.path.join(out_dir, "kernel_stats.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("Dose Kernel Statistics\n")
        f.write("=" * 60 + "\n\n")
        f.write("Units: MeV/primary/voxel (not Gy). See voxel_volume_cm3 and density_for_Gy_conversion in JSON.\n\n")
        f.write("Energy:\n")
        f.write(f"  total_energy_MeV:           {stats['total_energy_MeV']:.4e}\n")
        f.write(f"  total_energy_per_primary:   {stats['total_energy_per_primary_MeV']:.6e} MeV\n")
        f.write(f"  energy_in_grid_MeV:         {stats['energy_in_voxel_grid_MeV']:.4e}\n")
        f.write(f"  energy_outside_grid_MeV:    {stats['energy_outside_grid_MeV']:.4e}\n")
        if stats.get("energy_outside_clamped"):
            f.write("  (clamped to 0; was tiny negative from float roundoff)\n")
        f.write("\n")
        f.write("Primaries / events:\n")
        f.write(f"  n_primaries:                {stats['n_primaries']:,}\n")
        f.write(f"  n_events:                  {stats['n_events']:,}\n")
        if stats["n_events_vs_n_primaries_warning"]:
            f.write("  WARNING: n_events != n_primaries (see n_events_vs_n_primaries_warning)\n")
        f.write("\nGrid:\n")
        f.write(f"  bounds: x=[{bounds[0]:.2f},{bounds[1]:.2f}], y=[{bounds[2]:.2f},{bounds[3]:.2f}], z=[{bounds[4]:.2f},{bounds[5]:.2f}] cm\n")
        f.write(f"  grid_shape: {nx} x {ny} x {nz}\n")
        f.write(f"  voxel_size_nominal_cm: {dv:.4f}\n")
        f.write(f"  voxel_volume_cm3: {voxel_volume_cm3:.6e}\n\n")
        f.write("Kernel:\n")
        f.write(f"  max:          {stats['kernel_stats']['max']:.6e}\n")
        f.write(f"  mean_nonzero: {stats['kernel_stats']['mean_nonzero']:.6e}\n")
        f.write(f"  total_sum:    {stats['kernel_stats']['total_sum_MeV_per_primary']:.6e} MeV/primary\n\n")
        f.write("Uncertainty:\n")
        f.write(f"  mode: {uncertainty_mode}\n")
        f.write(f"  sigma_definition: {sigma_definition}\n")
        f.write("\nRun info:\n")
        f.write(f"  dose_path:  {dose_path}\n")
        f.write(f"  config_path: {config_path}\n")
        f.write(f"  timestamp:  {stats['run_info']['timestamp']}\n")
        f.write("=" * 60 + "\n")


def print_summary(n_primaries, n_events, total_energy, K, dv, warning=False):
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"  Total energy (file): {total_energy:.4e} MeV")
    print(f"  Total energy per primary: {total_energy / n_primaries:.6e} MeV" if n_primaries else "  N/A")
    print(f"  N_primaries: {n_primaries:,}")
    print(f"  N_events (unique in dose): {n_events:,}")
    if warning:
        print("  WARNING: n_events != n_primaries (see kernel_stats.json)")
    print(f"  Voxel size (cm): {dv:.4f}")
    print(f"  Kernel max: {np.nanmax(K):.6e} MeV/primary/voxel")
    if np.any(K > 0):
        print(f"  Kernel mean (non-zero): {np.nanmean(K[K > 0]):.6e} MeV/primary/voxel")
    print("=" * 60)


def main():
    args = parse_args()
    dose_path = os.path.abspath(args.dose)
    config_path = os.path.abspath(args.config)
    out_dir = os.path.abspath(args.output_dir)
    use_dxdydz = args.use_dxdydz
    use_xyz = not use_dxdydz  # default: (x,y,z) to match Cherenkov
    xy_range = tuple(args.xy_range) if args.xy_range is not None else None

    if not os.path.isfile(dose_path):
        print(f"ERROR: Dose file not found: {dose_path}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(out_dir, exist_ok=True)
    print(f"Output directory: {out_dir}")

    run_meta = load_run_meta(dose_path)
    header_path = path_header(dose_path)
    n_primaries = get_n_primaries(run_meta, config_path, header_path, args.n_primaries)
    print(f"N_primaries: {n_primaries:,}")

    if use_xyz:
        # Default: same bounds and center as Cherenkov (config geometry)
        if not os.path.isfile(config_path):
            print(f"ERROR: Config required for (x,y,z) mode: {config_path}", file=sys.stderr)
            sys.exit(1)
        water_size, water_pos = load_config(config_path)
        bounds, grid_center = get_water_bounds(water_size, water_pos, xy_range=xy_range)
        coord_labels = ("x", "y", "z")
        print(f"Bounds (world x,y,z, same as Cherenkov): x=[{bounds[0]:.1f},{bounds[1]:.1f}], y=[{bounds[2]:.1f},{bounds[3]:.1f}], z=[{bounds[4]:.1f},{bounds[5]:.1f}]")
        print("Counting unique event_id in dose...")
        n_events = count_unique_events_chunked(dose_path, args.chunk_size)
        print(f"N_events (unique event_id in dose): {n_events:,}")
    else:
        # --use-dxdydz: (dx,dy,dz) relative to primary, data-driven bounds, center = (0,0,0)
        print("Scanning (dx,dy,dz) range from data (chunked)...")
        bounds, _total_rec, n_events = scan_dose_bounds_chunked(dose_path, use_xyz=False, chunk_size=args.chunk_size)
        grid_center = (0.0, 0.0, 0.0)
        coord_labels = ("dx", "dy", "dz")
        print(f"Bounds (dx,dy,dz from data): x=[{bounds[0]:.2f},{bounds[1]:.2f}], y=[{bounds[2]:.2f},{bounds[3]:.2f}], z=[{bounds[4]:.2f},{bounds[5]:.2f}]")
        print(f"N_events (unique event_id in dose): {n_events:,}")

    n_events_vs_n_primaries_warning = n_events != n_primaries
    if n_events_vs_n_primaries_warning:
        print("WARNING: n_events != n_primaries; continuing and writing warning to kernel_stats.json.", file=sys.stderr)

    edges, dv = get_voxel_edges(bounds)
    x_edges, y_edges, z_edges = edges
    print(f"Voxel size (dv): {dv:.4f} cm")
    print(f"Grid shape: {len(x_edges)-1} x {len(y_edges)-1} x {len(z_edges)-1}")

    print("Building 3D weighted histogram (chunked)...")
    sum_w, sum_w2, energy_in_grid, energy_outside, total_records = build_dose_histogram_chunked(
        dose_path, edges, args.chunk_size, use_xyz
    )
    total_energy_MeV = energy_in_grid + energy_outside
    energy_outside_clamped = energy_outside < 0
    if energy_outside_clamped:
        energy_outside = 0.0
        total_energy_MeV = energy_in_grid
    print(f"Records read: {total_records:,}")
    print(f"Total energy: {total_energy_MeV:.4e} MeV (in grid: {energy_in_grid:.4e}, outside: {energy_outside:.4e})")

    K = sum_w / n_primaries
    uncertainty_mode = args.uncertainty_mode
    uncertainty_approximate = True
    sigma_definition = (
        "sigma = sqrt(sum_w2) / N_primaries (approximate, ignores within-event correlation)"
    )
    if uncertainty_mode == "fast":
        sigma = compute_kernel_fast(sum_w, sum_w2, n_primaries)[1]
    else:
        print("Computing event-level uncertainty (Welford)...")
        sigma, n_events_used = build_event_level_uncertainty(dose_path, edges, args.chunk_size, use_xyz, n_primaries)
        uncertainty_approximate = False
        sigma_definition = "sigma = std_e[E_e] / sqrt(N_events), ddof=1 (event-level)"
        print(f"Events used for uncertainty: {n_events_used:,}")

    print("Saving arrays...")
    save_arrays(out_dir, sum_w, K, sigma, edges, uncertainty_approximate=uncertainty_approximate)

    save_kernel_stats(
        out_dir,
        sum_w=sum_w,
        K=K,
        sigma=sigma,
        edges=edges,
        bounds=bounds,
        dv=dv,
        n_primaries=n_primaries,
        n_events=n_events,
        total_energy_MeV=total_energy_MeV,
        energy_in_grid=energy_in_grid,
        energy_outside=energy_outside,
        energy_outside_clamped=energy_outside_clamped,
        uncertainty_mode=uncertainty_mode,
        uncertainty_approximate=uncertainty_approximate,
        sigma_definition=sigma_definition,
        n_events_vs_n_primaries_warning=n_events_vs_n_primaries_warning,
        dose_path=dose_path,
        config_path=config_path,
        use_xyz=use_xyz,
        xy_range=xy_range,
    )

    print("Generating plots...")
    plot_slices_and_profiles(out_dir, K, edges, grid_center, coord_labels, dv)

    print_summary(n_primaries, n_events, total_energy_MeV, K, dv, warning=n_events_vs_n_primaries_warning)
    print(f"Done. Outputs in: {out_dir}")


if __name__ == "__main__":
    main()
