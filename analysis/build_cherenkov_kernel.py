#!/usr/bin/env python3
"""
Build 3D Cherenkov production voxel kernel K(x,y,z) from Geant4 binary PHSP.

Uses only InitialX, InitialY, InitialZ. Supports chunked reading for very large
files. Reads run_meta.json for total_photons and N_primaries when available.
Outputs: kernel_01_counts.npy, kernel_02_normalized.npy, kernel_03_uncertainty.npy,
kernel_04_voxel_edges.npz, and PNG plots (plot_01_xy_slice_center_z.png, etc.) in kernel_output/.

Usage:
  python build_cherenkov_kernel.py --n-primaries 52302569   # if no run_meta
  python build_cherenkov_kernel.py                         # with run_meta in same dir as phsp
  python build_cherenkov_kernel.py --phsp /path/to/file.phsp --config /path/to/config.json
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
# Constants (v2: 60 bytes per photon, compound dtype)
# -----------------------------------------------------------------------------
BYTES_PER_PHOTON = 60

PHSP_DTYPE = np.dtype([
    ("initX", "<f4"), ("initY", "<f4"), ("initZ", "<f4"),
    ("initDirX", "<f4"), ("initDirY", "<f4"), ("initDirZ", "<f4"),
    ("finalX", "<f4"), ("finalY", "<f4"), ("finalZ", "<f4"),
    ("finalDirX", "<f4"), ("finalDirY", "<f4"), ("finalDirZ", "<f4"),
    ("finalEnergy", "<f4"),
    ("event_id", "<u4"),
    ("track_id", "<i4"),
])
VOXEL_SIZE_MIN_CM = 0.3
VOXEL_SIZE_MAX_CM = 0.8
TARGET_BINS_LARGEST_DIM = 100
DEFAULT_CHUNK_PHOTONS = 1_000_000


def _script_dir():
    return os.path.dirname(os.path.abspath(__file__))


def parse_args():
    """Parse command-line arguments with defaults from project layout."""
    root = _script_dir()
    p = argparse.ArgumentParser(description="Build 3D Cherenkov voxel kernel from binary PHSP.")
    p.add_argument("--phsp", default=os.path.join(root, "output", "cherenkov_photons_full.phsp"),
                   help="Path to .phsp binary file")
    p.add_argument("--config", default=os.path.join(root, "config.json"),
                   help="Path to config.json")
    p.add_argument("--output-dir", default=os.path.join(root, "kernel_output"),
                   help="Output directory for kernel arrays and plots")
    p.add_argument("--n-primaries", type=int, default=None,
                   help="Number of primary particles (required if not in run_meta)")
    p.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_PHOTONS,
                   help=f"Photons per read chunk (default {DEFAULT_CHUNK_PHOTONS})")
    p.add_argument("--xy-range", nargs=2, type=float, default=None, metavar=("MIN", "MAX"),
                   help="Override x,y bounds to [MIN, MAX] (e.g. --xy-range -10 10 for beam-focused region; ~96%% of particles within 10 cm)")
    return p.parse_args()


def path_run_meta(phsp_path):
    """Same directory, same basename, .run_meta.json."""
    base = os.path.splitext(phsp_path)[0]
    return base + ".run_meta.json"


def path_header(phsp_path):
    """Same directory, same basename, .header."""
    base = os.path.splitext(phsp_path)[0]
    return base + ".header"


def load_run_meta(phsp_path):
    """Load run_meta.json if present. Returns dict or None."""
    path = path_run_meta(phsp_path)
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
    """
    Plan: x_min = cx - sx/2, x_max = cx + sx/2 (same for y, z).
    If xy_range=(min, max) is given, override x,y bounds only (beam-focused region).
    water_center (cx, cy, cz) always comes from water_position_cm (e.g. z=30 for water center).
    Returns (x_min, x_max, y_min, y_max, z_min, z_max), (cx, cy, cz).
    """
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
    bounds = (x_min, x_max, y_min, y_max, z_min, z_max)
    center = (cx, cy, cz)
    return bounds, center


def get_voxel_edges(bounds):
    """
    Plan: L_max = max(sx,sy,sz), dv = L_max/100 clamped to [0.3, 0.8].
    Use np.linspace(min, max, n_bins+1) to guarantee exact endpoints (avoids np.arange float drift).
    Returns (x_edges, y_edges, z_edges), dv.
    """
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


def _validate_header_if_present(phsp_path):
    """If .header exists, validate format_version 2 and bytes_per_photon 60."""
    hp = path_header(phsp_path)
    if not os.path.isfile(hp):
        return
    format_version = None
    bytes_per_photon = None
    with open(hp, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            for sep in (":", "="):
                if sep in line:
                    k, v = line.split(sep, 1)
                    k, v = k.strip().lower(), v.strip()
                    if "format_version" in k or k == "format_version":
                        try:
                            format_version = int(float(v))
                        except ValueError:
                            pass
                    elif "bytes_per_photon" in k or k == "bytes_per_photon":
                        try:
                            bytes_per_photon = int(float(v))
                        except ValueError:
                            pass
                    break
    if format_version is not None and format_version != 2:
        raise ValueError(
            f"Header format_version={format_version} is not v2; only v2 (60 bytes per photon) supported"
        )
    if bytes_per_photon is not None and bytes_per_photon != 60:
        raise ValueError(
            f"Header bytes_per_photon={bytes_per_photon} is not 60; only v2 supported"
        )


def get_n_photons(phsp_path, run_meta):
    """
    Validate file_size % 60 == 0; return n_photons = file_size // 60.
    If run_meta exists with total_photons, validate match.
    """
    file_size = os.path.getsize(phsp_path)
    if file_size % BYTES_PER_PHOTON != 0:
        raise ValueError(
            f"PHSP file size {file_size} is not divisible by {BYTES_PER_PHOTON}; "
            f"expected v2 format (60 bytes per photon)"
        )
    _validate_header_if_present(phsp_path)
    from_file = file_size // BYTES_PER_PHOTON
    if run_meta is not None and "total_photons" in run_meta:
        n_meta = int(run_meta["total_photons"])
        if n_meta != from_file:
            raise ValueError(f"run_meta total_photons={n_meta} != file_size//60={from_file}")
        return n_meta
    return from_file


def _validate_n_primaries(n):
    """Ensure N_primaries is a positive integer."""
    n = int(n)
    if n <= 0:
        raise ValueError(f"N_primaries must be positive, got {n}")
    return n


def get_n_primaries(run_meta, config_path, header_path, argparse_n_primaries):
    """
    Plan: (1) run_meta["events"] if present; (2) header; (3) config.simulation; (4) argparse.
    Returns validated positive integer.
    """
    if run_meta is not None and "events" in run_meta:
        return _validate_n_primaries(run_meta["events"])
    if header_path and os.path.isfile(header_path):
        # Simple key: value or key=value parser
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


def build_histogram_chunked(phsp_path, edges, chunk_size):
    """
    Read v2 phsp in chunks; extract initX, initY, initZ; np.histogramdd.
    Returns counts (3D), and total photons read from file.
    """
    x_edges, y_edges, z_edges = edges
    bins = (x_edges, y_edges, z_edges)
    shape = (len(x_edges) - 1, len(y_edges) - 1, len(z_edges) - 1)
    counts = np.zeros(shape, dtype=np.float64)
    bytes_per_chunk = chunk_size * BYTES_PER_PHOTON
    file_size = os.path.getsize(phsp_path)
    n_photons_total = file_size // BYTES_PER_PHOTON
    total_read = 0
    with open(phsp_path, "rb") as f:
        chunk_idx = 0
        while True:
            raw = f.read(bytes_per_chunk)
            if not raw:
                break
            n_read = len(raw) // BYTES_PER_PHOTON
            if n_read == 0:
                break
            data = np.frombuffer(raw, dtype=PHSP_DTYPE)
            xyz = np.column_stack([data["initX"], data["initY"], data["initZ"]])
            H, _ = np.histogramdd(xyz, bins=bins)
            counts += H
            total_read += n_read
            chunk_idx += 1
            if chunk_idx % 100 == 0 or total_read >= n_photons_total:
                print(f"  Processed {total_read:,} / {n_photons_total:,} photons ...", end="\r")
    print()
    return counts, total_read


def compute_kernel_and_uncertainty(counts, n_primaries):
    """K = counts / N_primaries; sigma = sqrt(counts) / N_primaries (zeros where counts==0)."""
    K = counts / n_primaries
    sigma = np.sqrt(np.maximum(counts, 0.0)) / n_primaries
    return K, sigma


def save_arrays(out_dir, counts, K, sigma, edges):
    """Save kernel_01_counts, kernel_02_normalized, kernel_03_uncertainty, kernel_04_voxel_edges."""
    # kernel_01: counts (3D array)
    np.save(os.path.join(out_dir, "kernel_01_counts.npy"), counts)
    # kernel_02: normalized K = counts / N_primaries
    np.save(os.path.join(out_dir, "kernel_02_normalized.npy"), K)
    # kernel_03: Poisson uncertainty sigma = sqrt(counts) / N_primaries
    np.save(os.path.join(out_dir, "kernel_03_uncertainty.npy"), sigma)
    x_edges, y_edges, z_edges = edges
    # kernel_04: voxel bin edges (x_edges, y_edges, z_edges)
    np.savez(
        os.path.join(out_dir, "kernel_04_voxel_edges.npz"),
        x_edges=x_edges,
        y_edges=y_edges,
        z_edges=z_edges,
    )


def voxel_centers(edges):
    """Return (x_centers, y_centers, z_centers) 1D arrays."""
    return [
        (edges[i][:-1] + edges[i][1:]) / 2
        for i in range(3)
    ]


def plot_slices_and_profiles(out_dir, K, sigma, edges, water_center, dv):
    """
    Plan: XY slice at z=cz; XZ slice at y=cy; depth K(z); radial K(r) with r = sqrt((x-cx)^2+(y-cy)^2).
    Output: plot_01_xy_slice_center_z.png, plot_02_xz_slice_center_y.png,
            plot_03_depth_profile_Kz.png, plot_04_radial_profile_Kr.png
    """
    x_edges, y_edges, z_edges = edges
    cx, cy, cz = water_center
    x_c, y_c, z_c = voxel_centers(edges)
    nx, ny, nz = K.shape

    # Index for slice at water center: find bin containing cz / cy
    k_center_z = np.searchsorted(z_edges, cz, side="right") - 1
    k_center_z = np.clip(k_center_z, 0, nz - 1)
    j_center_y = np.searchsorted(y_edges, cy, side="right") - 1
    j_center_y = np.clip(j_center_y, 0, ny - 1)

    # plot_01: XY slice at center Z (water center z = cz)
    # Colorbar: K = mean photons per primary per voxel (normalized kernel value)
    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.pcolormesh(x_edges, y_edges, K[:, :, k_center_z].T, shading="auto", cmap="viridis")
    ax.set_xlabel("x (cm)")
    ax.set_ylabel("y (cm)")
    ax.set_title(f"K(x,y) at z = {cz} cm (water center)")
    ax.set_aspect("equal")
    plt.colorbar(im, ax=ax, label="K (photons per primary per voxel)")
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "plot_01_xy_slice_center_z.png"), dpi=150, bbox_inches="tight")
    plt.close()

    # plot_02: XZ slice at center Y (water center y = cy)
    # Colorbar: same physical meaning as plot_01
    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.pcolormesh(x_edges, z_edges, K[:, j_center_y, :].T, shading="auto", cmap="viridis")
    ax.set_xlabel("x (cm)")
    ax.set_ylabel("z (cm)")
    ax.set_title(f"K(x,z) at y = {cy} cm (water center)")
    plt.colorbar(im, ax=ax, label="K (photons per primary per voxel)")
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "plot_02_xz_slice_center_y.png"), dpi=150, bbox_inches="tight")
    plt.close()

    # plot_03: depth profile K(z) — sum of K over x,y at each z (integrated xy cross-section)
    # Y-axis: photons per primary, integrated over the xy plane at that z
    Kz = np.sum(K, axis=(0, 1))
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(z_c, Kz, "b-", label="K(z)")
    ax.set_xlabel("z (cm)")
    ax.set_ylabel(r"$\sum_{x,y} K$ (photons per primary)")
    ax.set_title("Depth profile: K integrated over x,y at each z")
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "plot_03_depth_profile_Kz.png"), dpi=150, bbox_inches="tight")
    plt.close()

    # plot_04: radial profile K(r) — sum of K in each radial bin; r = sqrt((x-cx)^2+(y-cy)^2)
    # Y-axis: photons per primary, summed in each radial bin
    xx, yy, zz = np.meshgrid(x_c, y_c, z_c, indexing="ij")
    r = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    r_flat = r.ravel()
    K_flat = K.ravel()
    r_max = np.max(r)
    r_edges = np.linspace(0, r_max + 1e-9, 51)
    Kr, _ = np.histogram(r_flat, bins=r_edges, weights=K_flat)
    r_centers = (r_edges[:-1] + r_edges[1:]) / 2
    Kr_sum = Kr
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(r_centers, Kr_sum, "b-", label="K(r)")
    ax.set_xlabel("r (cm)")
    ax.set_ylabel("K(r) (photons per primary, sum in radial bin)")
    ax.set_title("Radial profile K(r), r = sqrt((x-cx)^2+(y-cy)^2)")
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "plot_04_radial_profile_Kr.png"), dpi=150, bbox_inches="tight")
    plt.close()


def save_kernel_stats(
    out_dir,
    photons_read,
    photons_in_grid,
    n_primaries,
    bounds,
    edges,
    dv,
    counts,
    K,
    phsp_path,
    config_path,
    xy_range,
):
    """
    Save kernel statistics to kernel_stats.json and kernel_stats.txt.
    Includes photons outside voxel grid (due to boundary) and other run info.
    """
    n_outside = int(photons_read - photons_in_grid)
    frac_outside = n_outside / photons_read if photons_read > 0 else 0.0
    x_edges, y_edges, z_edges = edges
    nx, ny, nz = len(x_edges) - 1, len(y_edges) - 1, len(z_edges) - 1

    stats = {
        "photons_read": photons_read,
        "photons_in_voxel_grid": int(photons_in_grid),
        "photons_outside_grid": n_outside,
        "fraction_outside": round(frac_outside, 6),
        "n_primaries": n_primaries,
        "mean_photons_per_primary_file": round(photons_read / n_primaries, 4) if n_primaries else 0,
        "mean_photons_per_primary_in_grid": round(photons_in_grid / n_primaries, 4) if n_primaries else 0,
        "water_bounds_cm": {
            "x_min": bounds[0],
            "x_max": bounds[1],
            "y_min": bounds[2],
            "y_max": bounds[3],
            "z_min": bounds[4],
            "z_max": bounds[5],
        },
        "grid_shape": [nx, ny, nz],
        "voxel_edges_summary": {
            "x": {"min": float(x_edges[0]), "max": float(x_edges[-1]), "n_bins": nx},
            "y": {"min": float(y_edges[0]), "max": float(y_edges[-1]), "n_bins": ny},
            "z": {"min": float(z_edges[0]), "max": float(z_edges[-1]), "n_bins": nz},
        },
        "voxel_size_nominal_cm": dv,
        "kernel_stats": {
            "max": float(np.nanmax(K)),
            "mean_nonzero": float(np.nanmean(K[K > 0])) if np.any(K > 0) else 0.0,
            "total_sum": float(K.sum()),
        },
        "run_info": {
            "phsp_path": phsp_path,
            "config_path": config_path,
            "xy_range": list(xy_range) if xy_range is not None else None,
            "timestamp": datetime.now().isoformat(),
        },
    }

    json_path = os.path.join(out_dir, "kernel_stats.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)

    txt_path = os.path.join(out_dir, "kernel_stats.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("Kernel Statistics\n")
        f.write("=" * 60 + "\n\n")
        f.write("Photon counts:\n")
        f.write(f"  photons_read:              {stats['photons_read']:,}\n")
        f.write(f"  photons_in_voxel_grid:     {stats['photons_in_voxel_grid']:,}\n")
        f.write(f"  photons_outside_grid:      {stats['photons_outside_grid']:,}\n")
        f.write(f"  fraction_outside:          {stats['fraction_outside']:.6f}\n\n")
        f.write("Primaries and means:\n")
        f.write(f"  n_primaries:               {stats['n_primaries']:,}\n")
        f.write(f"  mean_photons_per_primary (file):   {stats['mean_photons_per_primary_file']:.4f}\n")
        f.write(f"  mean_photons_per_primary (in grid): {stats['mean_photons_per_primary_in_grid']:.4f}\n\n")
        f.write("Voxel grid:\n")
        f.write(f"  water_bounds: x=[{bounds[0]:.1f},{bounds[1]:.1f}], y=[{bounds[2]:.1f},{bounds[3]:.1f}], z=[{bounds[4]:.1f},{bounds[5]:.1f}] cm\n")
        f.write(f"  grid_shape:   {nx} x {ny} x {nz}\n")
        f.write(f"  voxel_size:   {dv:.4f} cm (nominal)\n\n")
        f.write("Kernel:\n")
        f.write(f"  max:          {stats['kernel_stats']['max']:.6e}\n")
        f.write(f"  mean_nonzero: {stats['kernel_stats']['mean_nonzero']:.6e}\n\n")
        f.write("Run info:\n")
        f.write(f"  phsp_path:    {phsp_path}\n")
        f.write(f"  config_path:  {config_path}\n")
        f.write(f"  xy_range:     {stats['run_info']['xy_range']}\n")
        f.write(f"  timestamp:    {stats['run_info']['timestamp']}\n")
        f.write("=" * 60 + "\n")


def print_summary(n_photons, n_primaries, dv, counts, K):
    """Separate file vs voxel-grid statistics; voxel size; kernel max/mean."""
    n_in_grid = int(counts.sum())
    mean_pp_file = n_photons / n_primaries if n_primaries else 0
    mean_pp_grid = n_in_grid / n_primaries if n_primaries else 0
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"  Total photons (file): {n_photons:,}")
    print(f"  Photons in voxel grid: {n_in_grid:,}")
    print(f"  Total primaries (N_primaries): {n_primaries:,}")
    print(f"  Mean photons per primary (file): {mean_pp_file:.2f}")
    print(f"  Mean photons per primary (in grid): {mean_pp_grid:.2f}")
    print(f"  Voxel size (cm): {dv:.4f}")
    print(f"  Kernel max voxel value: {np.nanmax(K):.6e}")
    print(f"  Kernel mean voxel value (over non-zero): {np.nanmean(K[K > 0]):.6e}" if np.any(K > 0) else "  Kernel mean: N/A (all zero)")
    print("=" * 60)


def main():
    args = parse_args()
    phsp_path = os.path.abspath(args.phsp)
    config_path = os.path.abspath(args.config)
    out_dir = os.path.abspath(args.output_dir)

    if not os.path.isfile(phsp_path):
        print(f"ERROR: PHSP file not found: {phsp_path}", file=sys.stderr)
        sys.exit(1)
    if not os.path.isfile(config_path):
        print(f"ERROR: Config file not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(out_dir, exist_ok=True)
    print(f"Output directory: {out_dir}")

    # Run meta and n_photons
    run_meta = load_run_meta(phsp_path)
    n_photons = get_n_photons(phsp_path, run_meta)
    print(f"Total photons (from run_meta or file): {n_photons:,}")

    # N_primaries
    header_path = path_header(phsp_path)
    n_primaries = get_n_primaries(run_meta, config_path, header_path, args.n_primaries)
    print(f"N_primaries: {n_primaries:,}")

    # Config: water bounds and center
    water_size, water_pos = load_config(config_path)
    xy_range = tuple(args.xy_range) if args.xy_range is not None else None
    bounds, water_center = get_water_bounds(water_size, water_pos, xy_range=xy_range)
    if xy_range is not None:
        print(f"Water bounds (xy overridden by --xy-range): x=[{bounds[0]:.1f},{bounds[1]:.1f}], y=[{bounds[2]:.1f},{bounds[3]:.1f}], z=[{bounds[4]:.1f},{bounds[5]:.1f}]")
    else:
        print(f"Water bounds: x=[{bounds[0]:.1f},{bounds[1]:.1f}], y=[{bounds[2]:.1f},{bounds[3]:.1f}], z=[{bounds[4]:.1f},{bounds[5]:.1f}]")

    # Voxel edges
    edges, dv = get_voxel_edges(bounds)
    x_edges, y_edges, z_edges = edges
    print(f"Voxel size (dv): {dv:.4f} cm")
    print(f"Grid shape: {len(x_edges)-1} x {len(y_edges)-1} x {len(z_edges)-1}")

    # Chunked histogram
    print("Building 3D histogram (chunked read)...")
    counts, total_read = build_histogram_chunked(phsp_path, edges, args.chunk_size)
    n_in_grid = int(counts.sum())
    print(f"Photons read: {total_read:,}")
    print(f"Photons in voxel grid: {n_in_grid:,}")

    # K and sigma
    K, sigma = compute_kernel_and_uncertainty(counts, n_primaries)

    # Save
    print("Saving arrays...")
    save_arrays(out_dir, counts, K, sigma, edges)

    # Save kernel stats (photons outside grid, bounds, run info)
    save_kernel_stats(
        out_dir,
        photons_read=total_read,
        photons_in_grid=n_in_grid,
        n_primaries=n_primaries,
        bounds=bounds,
        edges=edges,
        dv=dv,
        counts=counts,
        K=K,
        phsp_path=phsp_path,
        config_path=config_path,
        xy_range=xy_range,
    )
    print(f"Photons outside voxel grid: {total_read - n_in_grid:,}")

    # Plots
    print("Generating plots...")
    plot_slices_and_profiles(out_dir, K, sigma, edges, water_center, dv)

    # Summary
    print_summary(n_photons, n_primaries, dv, counts, K)
    print(f"Done. Outputs in: {out_dir}")


if __name__ == "__main__":
    main()
