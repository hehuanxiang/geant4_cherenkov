#!/usr/bin/env python3
"""
Cherenkov Photon Analysis - Modularized Version
Clean architecture with separate data loading and plotting functions

Usage:
  python analyze_cherenkov_fast_v3.py              # Generate all 15 plots
  python analyze_cherenkov_fast_v3.py 2             # Generate only plot 2
  python analyze_cherenkov_fast_v3.py 5 10 14       # Generate plots 5, 10, 14
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

# ============= Configuration =============
BINARY_FILE = '/home/xhh2c/project/geant4_cherenkov/output/cherenkov_photons_full.phsp'
OUTPUT_DIR = '/home/xhh2c/project/geant4_cherenkov/plot'
SAMPLE_RATE = 10

os.makedirs(OUTPUT_DIR, exist_ok=True)
plt.style.use('seaborn-v0_8-whitegrid')
sns.set_palette("husl")

# ============= Data Loading =============
def load_and_process_data(sample_rate=SAMPLE_RATE):
    """Load binary PHSP and compute all derived quantities. Returns a dict with all arrays."""
    print(f"Reading every {sample_rate}th photon for speed...\n")
    
    # Load binary data
    print(f"Reading: {BINARY_FILE}")
    raw_data = np.fromfile(BINARY_FILE, dtype='float32')
    raw_data = raw_data.reshape(-1, 13)
    
    # Sample data
    if sample_rate > 1:
        raw_data = raw_data[::sample_rate]
    
    print(f"Loaded {len(raw_data):,} photon records (sampled)\n")
    
    # Extract raw arrays (13 fields)
    init_x = raw_data[:, 0]
    init_y = raw_data[:, 1]
    init_z = raw_data[:, 2]
    init_dir_x = raw_data[:, 3]
    init_dir_y = raw_data[:, 4]
    init_dir_z = raw_data[:, 5]
    final_x = raw_data[:, 6]
    final_y = raw_data[:, 7]
    final_z = raw_data[:, 8]
    final_dir_x = raw_data[:, 9]
    final_dir_y = raw_data[:, 10]
    final_dir_z = raw_data[:, 11]
    energy_array = raw_data[:, 12] / 1e12  # Convert microeV to MeV
    
    # Compute derived quantities
    print("Computing metrics...")
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
    
    print(f"Energy: {energy_array.min():.3e} - {energy_array.max():.3e} MeV")
    print(f"Displacement: {displacement.min():.2f} - {displacement.max():.2f} cm\n")
    
    return {
        'energy': energy_array,
        'init_x': init_x,
        'init_y': init_y,
        'init_z': init_z,
        'final_x': final_x,
        'final_y': final_y,
        'final_z': final_z,
        'init_dir_x': init_dir_x,
        'init_dir_y': init_dir_y,
        'init_dir_z': init_dir_z,
        'final_dir_x': final_dir_x,
        'final_dir_y': final_dir_y,
        'final_dir_z': final_dir_z,
        'displacement': displacement,
        'angle_change': angle_change,
        'theta_init': theta_init,
        'phi_init': phi_init,
    }

# ============= Utility Functions =============
def save_figure(plot_num, filename):
    """Save and close current figure"""
    filepath = f'{OUTPUT_DIR}/{filename}'
    plt.tight_layout()
    plt.savefig(filepath, dpi=300, bbox_inches='tight')
    print(f"  {plot_num:2d}/15: {filename.replace('_', ' ').rsplit('.', 1)[0]}")
    plt.close()

# ============= Plot Functions =============
def plot_01_energy_distribution(data):
    """Plot 1: Energy Distribution (Final Energy at Exit)"""
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.hist(data['energy'], bins=150, edgecolor='black', alpha=0.7, color='steelblue')
    ax.set_xlabel('Photon Final Energy (MeV)', fontsize=12)
    ax.set_ylabel('Count', fontsize=12)
    ax.set_title('Cherenkov Photon Energy Distribution\n(Final Energy at Exit Point)', fontsize=14, fontweight='bold')
    ax.set_yscale('log')
    ax.grid(True, alpha=0.3)
    return '01_energy_distribution.png'

def plot_02_init_position_xy(data):
    """Plot 2: Initial Position X-Y with colorbar"""
    fig, ax = plt.subplots(figsize=(10, 10))
    h = ax.hist2d(data['init_x'], data['init_y'], bins=100, cmap='inferno')
    ax.set_xlabel('Initial X (cm)', fontsize=12)
    ax.set_ylabel('Initial Y (cm)', fontsize=12)
    ax.set_title('Cherenkov Photon Production Location: X-Y Plane\n(Color = Photon Density)', 
                 fontsize=14, fontweight='bold')
    cbar = plt.colorbar(h[3], ax=ax, label='Count', shrink=0.9)
    ax.set_aspect('equal')
    return '02_init_position_xy.png'

def plot_03_init_position_z(data):
    """Plot 3: Initial Position Z Distribution"""
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.hist(data['init_z'], bins=100, edgecolor='black', alpha=0.7, color='coral')
    ax.set_xlabel('Initial Z (cm)', fontsize=12)
    ax.set_ylabel('Count', fontsize=12)
    ax.set_title('Photon Production Position: Z Distribution', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    return '03_init_position_z.png'

def plot_04_direction_distribution(data):
    """Plot 4: Direction Distribution"""
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.hist(data['phi_init'], bins=100, edgecolor='black', alpha=0.7, color='green', label='Polar angle')
    ax.hist(data['theta_init'], bins=100, edgecolor='black', alpha=0.5, color='blue', label='Azimuthal angle')
    ax.set_xlabel('Angle (degrees)', fontsize=12)
    ax.set_ylabel('Count', fontsize=12)
    ax.set_title('Initial Photon Direction Distribution', fontsize=14, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)
    return '04_direction_distribution.png'

def plot_05_displacement_distance(data):
    """Plot 5: Displacement Distance"""
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.hist(data['displacement'], bins=100, edgecolor='black', alpha=0.7, color='darkgreen')
    ax.set_xlabel('Displacement Distance (cm)', fontsize=12)
    ax.set_ylabel('Count', fontsize=12)
    ax.set_title('Photon Displacement: Initial to Final Position', fontsize=14, fontweight='bold')
    ax.set_yscale('log')
    ax.grid(True, alpha=0.3)
    return '05_displacement_distance.png'

def plot_06_direction_change_angle(data):
    """Plot 6: Direction Change Angle"""
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.hist(data['angle_change'], bins=100, edgecolor='black', alpha=0.7, color='purple')
    ax.set_xlabel('Direction Change Angle (degrees)', fontsize=12)
    ax.set_ylabel('Count', fontsize=12)
    ax.set_title('Photon Direction Change During Transport', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    return '06_direction_change_angle.png'

def plot_07_final_position_xy(data):
    """Plot 7: Final Position X-Y"""
    fig, ax = plt.subplots(figsize=(10, 10))
    h = ax.hist2d(data['final_x'], data['final_y'], bins=100, cmap='viridis')
    ax.set_xlabel('Final X (cm)', fontsize=12)
    ax.set_ylabel('Final Y (cm)', fontsize=12)
    ax.set_title('Photon Final Position: X-Y Plane\n(Color = Photon Density)', 
                 fontsize=14, fontweight='bold')
    cbar = plt.colorbar(h[3], ax=ax, label='Count', shrink=0.9)
    ax.set_aspect('equal')
    return '07_final_position_xy.png'

def plot_08_final_position_z(data):
    """Plot 8: Final Position Z Distribution"""
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.hist(data['final_z'], bins=100, edgecolor='black', alpha=0.7, color='orange')
    ax.set_xlabel('Final Z (cm)', fontsize=12)
    ax.set_ylabel('Count', fontsize=12)
    ax.set_title('Photon Final Position: Z Distribution', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    return '08_final_position_z.png'

def plot_09_displacement_vs_energy(data):
    """Plot 9: Energy vs Displacement Scatter"""
    fig, ax = plt.subplots(figsize=(12, 7))
    scatter = ax.scatter(data['energy'], data['displacement'], 
                        c=data['angle_change'], cmap='rainbow', alpha=0.4, s=15)
    ax.set_xlabel('Photon Energy (MeV)', fontsize=12)
    ax.set_ylabel('Displacement Distance (cm)', fontsize=12)
    ax.set_title('Photon Displacement vs Energy (colored by direction change)', 
                fontsize=14, fontweight='bold')
    plt.colorbar(scatter, ax=ax, label='Direction Change (deg)')
    ax.set_yscale('log')
    ax.grid(True, alpha=0.3)
    return '09_displacement_vs_energy.png'

def plot_10_position_correlation(data):
    """Plot 10: Position Correlation"""
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    
    axes[0].scatter(data['init_x'], data['final_x'], alpha=0.3, s=10, color='steelblue', label='Photons')
    lims_x = [min(data['init_x'].min(), data['final_x'].min()), 
              max(data['init_x'].max(), data['final_x'].max())]
    axes[0].plot(lims_x, lims_x, 'r--', lw=2, label='No displacement (y=x)')
    axes[0].set_xlabel('Initial X (cm)', fontsize=11)
    axes[0].set_ylabel('Final X (cm)', fontsize=11)
    axes[0].set_title('X Position: Initial vs Final', fontsize=12, fontweight='bold')
    axes[0].legend(loc='upper left', fontsize=10)
    axes[0].grid(True, alpha=0.3)

    axes[1].scatter(data['init_y'], data['final_y'], alpha=0.3, s=10, color='coral', label='Photons')
    lims_y = [min(data['init_y'].min(), data['final_y'].min()), 
              max(data['init_y'].max(), data['final_y'].max())]
    axes[1].plot(lims_y, lims_y, 'r--', lw=2, label='No displacement (y=x)')
    axes[1].set_xlabel('Initial Y (cm)', fontsize=11)
    axes[1].set_ylabel('Final Y (cm)', fontsize=11)
    axes[1].set_title('Y Position: Initial vs Final', fontsize=12, fontweight='bold')
    axes[1].legend(loc='upper left', fontsize=10)
    axes[1].grid(True, alpha=0.3)
    
    return '10_position_correlation.png'

def plot_11_3d_initial_position(data):
    """Plot 11: 3D Initial Position (Interactive HTML)"""
    sample_idx = np.random.choice(len(data['init_x']), min(20000, len(data['init_x'])), replace=False)
    fig = go.Figure(data=[go.Scatter3d(
        x=data['init_x'][sample_idx],
        y=data['init_y'][sample_idx],
        z=data['init_z'][sample_idx],
        mode='markers',
        marker=dict(size=2, color=data['energy'][sample_idx], colorscale='Viridis', showscale=True)
    )])
    fig.update_layout(title='3D Initial Position Distribution', width=1000, height=800,
                      scene=dict(xaxis_title='X (cm)', yaxis_title='Y (cm)', zaxis_title='Z (cm)'))
    filepath = f'{OUTPUT_DIR}/11_3d_initial_position.html'
    fig.write_html(filepath)
    print(f"  11/15: 3d_initial_position")
    return None  # Custom save

def plot_12_3d_correlations(data):
    """Plot 12: 3D Energy-Displacement-Angle (Interactive HTML)"""
    sample_idx = np.random.choice(len(data['energy']), min(20000, len(data['energy'])), replace=False)
    fig = go.Figure(data=[go.Scatter3d(
        x=data['energy'][sample_idx],
        y=data['displacement'][sample_idx],
        z=data['angle_change'][sample_idx],
        mode='markers',
        marker=dict(size=2, color=data['init_z'][sample_idx], colorscale='Plasma', showscale=True)
    )])
    fig.update_layout(title='Energy vs Displacement vs Direction Change', width=1000, height=800,
                      scene=dict(xaxis_title='Energy (MeV)', yaxis_title='Displacement (cm)', 
                                 zaxis_title='Direction Change (deg)'))
    filepath = f'{OUTPUT_DIR}/12_3d_correlations.html'
    fig.write_html(filepath)
    print(f"  12/15: 3d_correlations")
    return None  # Custom save

def plot_13_spatial_clustering(data):
    """Plot 13: Spatial Clustering"""
    sample_size = min(100000, len(data['init_x']))
    sample_idx = np.random.choice(len(data['init_x']), sample_size, replace=False)
    
    positions = np.column_stack([data['init_x'][sample_idx], 
                                 data['init_y'][sample_idx], 
                                 data['init_z'][sample_idx]])
    clustering = DBSCAN(eps=3, min_samples=30).fit(positions)
    labels = clustering.labels_

    fig, ax = plt.subplots(figsize=(12, 10))
    scatter = ax.scatter(data['init_x'][sample_idx], data['init_y'][sample_idx], 
                        c=labels, cmap='tab20', s=20, alpha=0.6)
    ax.set_xlabel('Initial X (cm)', fontsize=12)
    ax.set_ylabel('Initial Y (cm)', fontsize=12)
    ax.set_title('Spatial Clustering of Photon Production (DBSCAN)', fontsize=14, fontweight='bold')
    plt.colorbar(scatter, ax=ax, label='Cluster ID')
    ax.set_aspect('equal')
    return '13_spatial_clustering.png'

def plot_14_joint_distributions(data):
    """Plot 14: Joint Distributions (6 hexbin subplots)"""
    fig, axes = plt.subplots(2, 3, figsize=(16, 10))

    axes[0, 0].hexbin(data['energy'], data['displacement'], gridsize=40, cmap='YlOrRd', mincnt=1)
    axes[0, 0].set_xlabel('Energy (MeV)', fontsize=10)
    axes[0, 0].set_ylabel('Displacement (cm)', fontsize=10)
    axes[0, 0].set_title('Energy vs Displacement', fontsize=11, fontweight='bold')
    axes[0, 0].set_yscale('log')

    axes[0, 1].hexbin(data['energy'], data['angle_change'], gridsize=40, cmap='YlGnBu', mincnt=1)
    axes[0, 1].set_xlabel('Energy (MeV)', fontsize=10)
    axes[0, 1].set_ylabel('Angle Change (deg)', fontsize=10)
    axes[0, 1].set_title('Energy vs Direction Change', fontsize=11, fontweight='bold')

    axes[0, 2].hexbin(data['displacement'], data['angle_change'], gridsize=40, cmap='PuBu', mincnt=1)
    axes[0, 2].set_xlabel('Displacement (cm)', fontsize=10)
    axes[0, 2].set_ylabel('Angle Change (deg)', fontsize=10)
    axes[0, 2].set_title('Displacement vs Direction Change', fontsize=11, fontweight='bold')
    axes[0, 2].set_xscale('log')

    axes[1, 0].hexbin(data['init_z'], data['displacement'], gridsize=40, cmap='RdPu', mincnt=1)
    axes[1, 0].set_xlabel('Initial Z (cm)', fontsize=10)
    axes[1, 0].set_ylabel('Displacement (cm)', fontsize=10)
    axes[1, 0].set_title('Initial Z vs Displacement', fontsize=11, fontweight='bold')
    axes[1, 0].set_yscale('log')

    axes[1, 1].hexbin(data['init_z'], data['energy'], gridsize=40, cmap='GnBu', mincnt=1)
    axes[1, 1].set_xlabel('Initial Z (cm)', fontsize=10)
    axes[1, 1].set_ylabel('Energy (MeV)', fontsize=10)
    axes[1, 1].set_title('Initial Z vs Energy', fontsize=11, fontweight='bold')

    axes[1, 2].hexbin(data['init_z'], data['angle_change'], gridsize=40, cmap='OrRd', mincnt=1)
    axes[1, 2].set_xlabel('Initial Z (cm)', fontsize=10)
    axes[1, 2].set_ylabel('Angle Change (deg)', fontsize=10)
    axes[1, 2].set_title('Initial Z vs Direction Change', fontsize=11, fontweight='bold')

    return '14_joint_distributions.png'

def plot_15_statistical_summary(data):
    """Plot 15: Statistical Summary"""
    fig = plt.figure(figsize=(14, 10))
    gs = fig.add_gridspec(3, 3, hspace=0.35, wspace=0.3)

    ax1 = fig.add_subplot(gs[0, 0])
    ax1.hist(data['energy'], bins=80, alpha=0.7, color='steelblue', edgecolor='black', label='Distribution')
    ax1.axvline(data['energy'].mean(), color='red', linestyle='--', linewidth=2, label='Mean')
    ax1.set_xlabel('Energy (MeV)', fontsize=9)
    ax1.set_ylabel('Count', fontsize=9)
    ax1.set_title('Energy', fontsize=10, fontweight='bold')
    ax1.set_yscale('log')
    ax1.legend(fontsize=8, loc='upper right')

    ax2 = fig.add_subplot(gs[0, 1])
    ax2.hist(data['displacement'], bins=80, alpha=0.7, color='coral', edgecolor='black', label='Distribution')
    ax2.axvline(data['displacement'].mean(), color='red', linestyle='--', linewidth=2, label='Mean')
    ax2.set_xlabel('Displacement (cm)', fontsize=9)
    ax2.set_ylabel('Count', fontsize=9)
    ax2.set_title('Displacement', fontsize=10, fontweight='bold')
    ax2.set_yscale('log')
    ax2.legend(fontsize=8, loc='upper right')

    ax3 = fig.add_subplot(gs[0, 2])
    ax3.hist(data['angle_change'], bins=80, alpha=0.7, color='green', edgecolor='black', label='Distribution')
    ax3.axvline(data['angle_change'].mean(), color='red', linestyle='--', linewidth=2, label='Mean')
    ax3.set_xlabel('Direction Change (deg)', fontsize=9)
    ax3.set_ylabel('Count', fontsize=9)
    ax3.set_title('Direction Change', fontsize=10, fontweight='bold')
    ax3.legend(fontsize=8, loc='upper right')

    ax4 = fig.add_subplot(gs[1, 0])
    h4 = ax4.hist2d(data['init_x'], data['init_y'], bins=100, cmap='inferno')
    ax4.set_xlabel('Initial X (cm)', fontsize=9)
    ax4.set_ylabel('Initial Y (cm)', fontsize=9)
    ax4.set_title('Initial X-Y', fontsize=10, fontweight='bold')
    ax4.set_aspect('equal')
    plt.colorbar(h4[3], ax=ax4, label='Count', shrink=0.8)

    ax5 = fig.add_subplot(gs[1, 1])
    h5 = ax5.hist2d(data['final_x'], data['final_y'], bins=100, cmap='viridis')
    ax5.set_xlabel('Final X (cm)', fontsize=9)
    ax5.set_ylabel('Final Y (cm)', fontsize=9)
    ax5.set_title('Final X-Y', fontsize=10, fontweight='bold')
    ax5.set_aspect('equal')
    plt.colorbar(h5[3], ax=ax5, label='Count', shrink=0.8)

    ax6 = fig.add_subplot(gs[1, 2])
    scatter = ax6.scatter(data['energy'], data['displacement'], c=data['angle_change'], cmap='rainbow', s=5, alpha=0.5)
    ax6.set_xlabel('Energy (MeV)', fontsize=9)
    ax6.set_ylabel('Displacement (cm)', fontsize=9)
    ax6.set_title('Energy-Displacement-Angle', fontsize=10, fontweight='bold')
    ax6.set_yscale('log')
    plt.colorbar(scatter, ax=ax6, label='Direction\nChange (deg)', shrink=0.8)

    ax7 = fig.add_subplot(gs[2, :])
    ax7.axis('off')

    stats_text = f"""STATISTICS  |  Total: {len(data['energy']):,} photons
Energy: Mean={data['energy'].mean():.2e}, Med={np.median(data['energy']):.2e}, Std={data['energy'].std():.2e} MeV | Range: [{data['energy'].min():.2e}, {data['energy'].max():.2e}]
Displacement: Mean={data['displacement'].mean():.2f}, Med={np.median(data['displacement']):.2f}, Std={data['displacement'].std():.2f} cm | Range: [{data['displacement'].min():.2f}, {data['displacement'].max():.2f}]
Direction Change: Mean={data['angle_change'].mean():.1f}, Med={np.median(data['angle_change']):.1f}, Std={data['angle_change'].std():.1f} deg | Range: [{data['angle_change'].min():.1f}, {data['angle_change'].max():.1f}]"""

    ax7.text(0.05, 0.5, stats_text, transform=ax7.transAxes, fontsize=9,
            fontfamily='monospace', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))

    return '15_statistical_summary.png'

# ============= Plot Registry =============
PLOTS = {
    1: plot_01_energy_distribution,
    2: plot_02_init_position_xy,
    3: plot_03_init_position_z,
    4: plot_04_direction_distribution,
    5: plot_05_displacement_distance,
    6: plot_06_direction_change_angle,
    7: plot_07_final_position_xy,
    8: plot_08_final_position_z,
    9: plot_09_displacement_vs_energy,
    10: plot_10_position_correlation,
    11: plot_11_3d_initial_position,
    12: plot_12_3d_correlations,
    13: plot_13_spatial_clustering,
    14: plot_14_joint_distributions,
    15: plot_15_statistical_summary,
}

# ============= Main Function =============
def main():
    # Parse command-line arguments
    plots_to_generate = None
    if len(sys.argv) > 1:
        try:
            plots_to_generate = [int(arg) for arg in sys.argv[1:]]
        except ValueError:
            print(f"Invalid plot number. Usage: python {sys.argv[0]} [plot_numbers...]")
            sys.exit(1)
    
    # Print header
    print("=" * 70)
    print("Cherenkov Photon Analysis - Fast Sampling Version")
    print("=" * 70)
    if plots_to_generate:
        print(f"DEBUG MODE: Generating only plots {plots_to_generate}\n")
    
    # Load data ONCE
    data = load_and_process_data(SAMPLE_RATE)
    
    # Generate plots
    print("Generating plots...")
    for plot_num in range(1, 16):
        if plots_to_generate is None or plot_num in plots_to_generate:
            if plot_num in PLOTS:
                try:
                    filename = PLOTS[plot_num](data)
                    if filename:  # Only save if filename is returned (not None for 3D plots)
                        save_figure(plot_num, filename)
                except Exception as e:
                    print(f"  ERROR generating plot {plot_num}: {e}")
    
    # Print footer
    print()
    print("=" * 70)
    print("Analysis Complete!")
    print("=" * 70)
    print(f"All plots saved to: {OUTPUT_DIR}/")
    print("=" * 70)

if __name__ == '__main__':
    main()
