#!/usr/bin/env python3
"""
Cherenkov Photon Analysis - Modularized Version (sampled for fast runs)
Clean architecture with separate data loading and plotting functions.
Uses v2 60B PHSP format.

Usage:
  python analysis/analyze_cherenkov_fast.py              # Generate all 15 plots
  python analysis/analyze_cherenkov_fast.py 2            # Generate only plot 2
  python analysis/analyze_cherenkov_fast.py 5 10 14      # Generate plots 5, 10, 14
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.graph_objects as go
from sklearn.cluster import DBSCAN
import os
import sys
import warnings
warnings.filterwarnings('ignore')

# Add project root for read_binary_phsp import
_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_script_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
from read_binary_phsp import read_binary_phsp

# ============= Configuration =============
BINARY_FILE = os.path.join(_project_root, 'output', 'cherenkov_photons_full.phsp')
OUTPUT_DIR = os.path.join(_project_root, 'plot')
SAMPLE_RATE = 10

os.makedirs(OUTPUT_DIR, exist_ok=True)
plt.style.use('seaborn-v0_8-whitegrid')
sns.set_palette("husl")


def load_and_process_data():
    """Load binary PHSP (v2, 60B), sample every SAMPLE_RATE records. Returns dict with arrays."""
    print("Loading sampled dataset from binary phase space file (v2)...\n")
    data = read_binary_phsp(BINARY_FILE)
    idx = np.arange(0, len(data), SAMPLE_RATE)
    data = data[idx]
    print(f"Loaded {len(data):,} sampled photon records (1/{SAMPLE_RATE})\n")

    init_x = data["initX"]
    init_y = data["initY"]
    init_z = data["initZ"]
    init_dir_x = data["initDirX"]
    init_dir_y = data["initDirY"]
    init_dir_z = data["initDirZ"]
    final_x = data["finalX"]
    final_y = data["finalY"]
    final_z = data["finalZ"]
    final_dir_x = data["finalDirX"]
    final_dir_y = data["finalDirY"]
    final_dir_z = data["finalDirZ"]
    energy_array = data["finalEnergy"] / 1e12  # microeV -> MeV

    displacement = np.sqrt(
        (final_x - init_x)**2 + (final_y - init_y)**2 + (final_z - init_z)**2
    )
    init_norm = np.sqrt(init_dir_x**2 + init_dir_y**2 + init_dir_z**2 + 1e-10)
    final_norm = np.sqrt(final_dir_x**2 + final_dir_y**2 + final_dir_z**2 + 1e-10)
    dot_products = (init_dir_x * final_dir_x + init_dir_y * final_dir_y + init_dir_z * final_dir_z) / (init_norm * final_norm)
    dot_products = np.clip(dot_products, -1, 1)
    angle_change = np.arccos(dot_products) * 180 / np.pi
    theta_init = np.degrees(np.arctan2(init_dir_y, init_dir_x))
    phi_init = np.degrees(np.arccos(np.clip(init_dir_z, -1, 1)))

    return {
        'energy': energy_array,
        'init_x': init_x, 'init_y': init_y, 'init_z': init_z,
        'final_x': final_x, 'final_y': final_y, 'final_z': final_z,
        'init_dir_x': init_dir_x, 'init_dir_y': init_dir_y, 'init_dir_z': init_dir_z,
        'final_dir_x': final_dir_x, 'final_dir_y': final_dir_y, 'final_dir_z': final_dir_z,
        'displacement': displacement,
        'angle_change': angle_change,
        'theta_init': theta_init,
        'phi_init': phi_init,
        'event_id': data["event_id"],
        'track_id': data["track_id"],
    }


if __name__ == "__main__":
    data = load_and_process_data()
    print("event_id range:", data["event_id"].min(), "-", data["event_id"].max())
    print("track_id range:", data["track_id"].min(), "-", data["track_id"].max())
