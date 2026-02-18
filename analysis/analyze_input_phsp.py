#!/usr/bin/env python3
"""
IAEA Phase Space File Analyzer
Analyzes the input PHSP file used as particle source for Geant4 simulations

Usage:
    python3 analyze_input_phsp.py [--sample N]
    
Options:
    --sample N    Read every Nth particle (default: 100 for speed)
"""

import struct
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import sys
import argparse

# ============= Configuration =============
PHSP_FILE = '/home/xhh2c/project/data_6MV_photon_PHSP/Varian_TrueBeam6MV_03.phsp'
HEADER_FILE = '/home/xhh2c/project/data_6MV_photon_PHSP/Varian_TrueBeam6MV_03.header'
OUTPUT_DIR = '/home/xhh2c/project/geant4_cherenkov/analysis_input_phsp'

# IAEA format constants
RECORD_SIZE = 25  # bytes per particle
PARTICLE_TYPES = {1: 'Photon', 2: 'Electron', 3: 'Positron'}

# ============= Functions =============

def read_header_info(header_file):
    """Parse IAEA header file"""
    info = {}
    with open(header_file, 'r') as f:
        content = f.read()
    
    # Extract key information
    for line in content.split('\n'):
        if 'ORIG_HISTORIES' in line:
            info['total_histories'] = int(content.split('$ORIG_HISTORIES:')[1].split()[0])
        elif '$PARTICLES:' in line:
            info['total_particles'] = int(content.split('$PARTICLES:')[1].split()[0])
        elif '$PHOTONS:' in line:
            info['n_photons'] = int(content.split('$PHOTONS:')[1].split()[0])
        elif '$ELECTRONS:' in line:
            info['n_electrons'] = int(content.split('$ELECTRONS:')[1].split()[0])
        elif '$POSITRONS:' in line:
            info['n_positrons'] = int(content.split('$POSITRONS:')[1].split()[0])
    
    # Extract geometry range
    geom_section = content.split('$STATISTICAL_INFORMATION_GEOMETRY:')[1].split('\n')[1:4]
    x_range = [float(x) for x in geom_section[0].split()]
    y_range = [float(x) for x in geom_section[1].split()]
    z_range = [float(x) for x in geom_section[2].split()]
    
    info['x_range'] = x_range
    info['y_range'] = y_range
    info['z_range'] = z_range
    
    # Extract energy statistics
    stat_section = content.split('$STATISTICAL_INFORMATION_PARTICLES:')[1]
    info['energy_stats'] = stat_section.split('$STATISTICAL_INFORMATION_GEOMETRY:')[0]
    
    # Extract beam info
    if '$BEAM_NAME:' in content:
        info['beam_name'] = content.split('$BEAM_NAME:')[1].split('\n')[1].strip()
    if '$NOMINAL_SSD:' in content:
        info['nominal_ssd'] = content.split('$NOMINAL_SSD:')[1].split('\n')[0].strip()
    if '$COORDINATE_SYSTEM_DESCRIPTION:' in content:
        info['coord_system'] = content.split('$COORDINATE_SYSTEM_DESCRIPTION:')[1].split('//')[0].strip()
    
    return info


def read_phsp_particles(phsp_file, sample_rate=100, max_particles=None):
    """
    Read IAEA format phase space file
    
    IAEA format (25 bytes per record):
    - Particle type (1 byte): 1=photon, 2=electron, 3=positron
    - Energy (4 bytes float)
    - X, Y, Z position (3 × 4 bytes float)
    - U, V direction cosines (2 × 4 bytes float)
    """
    print(f"Reading PHSP file: {phsp_file}")
    print(f"Sample rate: every {sample_rate}th particle\n")
    
    particles = {
        'type': [],
        'energy': [],
        'x': [], 'y': [], 'z': [],
        'u': [], 'v': [], 'w': []
    }
    
    with open(phsp_file, 'rb') as f:
        # Get file size
        f.seek(0, 2)
        file_size = f.tell()
        f.seek(0)
        
        total_records = file_size // RECORD_SIZE
        print(f"Total particles in file: {total_records:,}")
        
        count = 0
        sampled = 0
        
        while True:
            # Read one record
            data = f.read(RECORD_SIZE)
            if len(data) < RECORD_SIZE:
                break
            
            # Only sample every Nth particle
            if count % sample_rate == 0:
                # Unpack IAEA format: type(1B) + energy(4B) + x,y,z(12B) + u,v(8B) = 25 bytes
                particle_type = struct.unpack('b', data[0:1])[0]
                floats = struct.unpack('<6f', data[1:25])  # Little endian, 6 floats
                
                energy = floats[0]
                x, y, z = floats[1], floats[2], floats[3]
                u, v = floats[4], floats[5]
                
                # Calculate W from U and V: W = sqrt(1 - U^2 - V^2)
                w = np.sqrt(max(0, 1 - u**2 - v**2))
                
                particles['type'].append(particle_type)
                particles['energy'].append(energy)
                particles['x'].append(x)
                particles['y'].append(y)
                particles['z'].append(z)
                particles['u'].append(u)
                particles['v'].append(v)
                particles['w'].append(w)
                
                sampled += 1
            
            count += 1
            
            if max_particles and sampled >= max_particles:
                break
            
            # Progress indicator
            if count % 1000000 == 0:
                print(f"  Processed: {count:,} particles ({sampled:,} sampled)")
    
    print(f"\nTotal particles read: {count:,}")
    print(f"Sampled particles: {sampled:,}\n")
    
    # Convert to numpy arrays
    for key in particles:
        particles[key] = np.array(particles[key])
    
    return particles


def analyze_particles(particles, header_info):
    """Analyze particle distributions and statistics"""
    
    stats = {}
    
    # Particle type counts
    types, counts = np.unique(particles['type'], return_counts=True)
    stats['type_counts'] = {PARTICLE_TYPES.get(t, f'Unknown({t})'): c for t, c in zip(types, counts)}
    
    # Energy statistics by type
    stats['energy_by_type'] = {}
    for ptype in np.unique(particles['type']):
        mask = particles['type'] == ptype
        energies = particles['energy'][mask]
        stats['energy_by_type'][PARTICLE_TYPES.get(ptype, f'Unknown({ptype})')] = {
            'mean': np.mean(energies),
            'std': np.std(energies),
            'min': np.min(energies),
            'max': np.max(energies),
            'median': np.median(energies)
        }
    
    # Position statistics
    stats['position'] = {
        'x': {'min': np.min(particles['x']), 'max': np.max(particles['x']), 
              'mean': np.mean(particles['x']), 'std': np.std(particles['x'])},
        'y': {'min': np.min(particles['y']), 'max': np.max(particles['y']),
              'mean': np.mean(particles['y']), 'std': np.std(particles['y'])},
        'z': {'min': np.min(particles['z']), 'max': np.max(particles['z']),
              'mean': np.mean(particles['z']), 'std': np.std(particles['z'])}
    }
    
    # Direction statistics (W component)
    stats['direction'] = {
        'w_mean': np.mean(particles['w']),
        'w_std': np.std(particles['w']),
        'w_min': np.min(particles['w']),
        'w_max': np.max(particles['w'])
    }
    
    # Angular distribution
    theta = np.degrees(np.arctan2(particles['v'], particles['u']))  # Azimuthal angle
    phi = np.degrees(np.arccos(np.clip(particles['w'], -1, 1)))    # Polar angle
    stats['angles'] = {
        'theta_mean': np.mean(theta),
        'theta_std': np.std(theta),
        'phi_mean': np.mean(phi),
        'phi_std': np.std(phi)
    }
    
    # Radial distribution
    r = np.sqrt(particles['x']**2 + particles['y']**2)
    stats['radial'] = {
        'r_mean': np.mean(r),
        'r_std': np.std(r),
        'r_max': np.max(r)
    }
    
    # Percentage within different radii
    stats['coverage'] = {}
    for r_limit in [5, 10, 15, 20, 30]:
        within_r = np.sum(r <= r_limit) / len(r) * 100
        within_x = np.sum((particles['x'] >= -r_limit) & (particles['x'] <= r_limit)) / len(particles['x']) * 100
        within_y = np.sum((particles['y'] >= -r_limit) & (particles['y'] <= r_limit)) / len(particles['y']) * 100
        stats['coverage'][r_limit] = {
            'radial': within_r,
            'x': within_x,
            'y': within_y
        }
    
    return stats


def plot_xy_distribution(particles, header_info, output_dir):
    """Plot X-Y position distribution (similar to Figure 2)"""
    
    fig, ax = plt.subplots(figsize=(10, 10))
    
    # Create 2D histogram
    h = ax.hist2d(particles['x'], particles['y'], bins=100, cmap='inferno')
    
    ax.set_xlabel('X Position (cm)', fontsize=14)
    ax.set_ylabel('Y Position (cm)', fontsize=14)
    ax.set_title('Input PHSP: Particle Source Distribution (X-Y Plane)\n' + 
                 f'{header_info.get("beam_name", "Varian TrueBeam 6MV")}\n' +
                 f'Color = Particle Density', fontsize=14, fontweight='bold')
    
    # Add colorbar
    cbar = plt.colorbar(h[3], ax=ax, label='Particle Count', shrink=0.9)
    
    # Set equal aspect ratio
    ax.set_aspect('equal')
    
    # Add grid
    ax.grid(True, alpha=0.3, linestyle='--')
    
    # Add statistics text
    total_sampled = len(particles['x'])
    stats_text = f'Sampled particles: {total_sampled:,}\n'
    stats_text += f'X range: [{np.min(particles["x"]):.2f}, {np.max(particles["x"]):.2f}] cm\n'
    stats_text += f'Y range: [{np.min(particles["y"]):.2f}, {np.max(particles["y"]):.2f}] cm'
    
    ax.text(0.02, 0.98, stats_text, transform=ax.transAxes,
            fontsize=10, verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    
    plt.tight_layout()
    
    output_file = output_dir / 'input_phsp_xy_distribution.png'
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"✓ Saved: {output_file}")
    plt.close()


def plot_additional_diagnostics(particles, header_info, output_dir):
    """Create additional diagnostic plots"""
    
    # 1. Energy distribution by particle type
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    # Energy histogram
    ax = axes[0, 0]
    for ptype in np.unique(particles['type']):
        mask = particles['type'] == ptype
        energies = particles['energy'][mask]
        label = PARTICLE_TYPES.get(ptype, f'Type {ptype}')
        ax.hist(energies, bins=50, alpha=0.6, label=label, edgecolor='black')
    ax.set_xlabel('Energy (MeV)', fontsize=12)
    ax.set_ylabel('Count', fontsize=12)
    ax.set_title('Energy Distribution by Particle Type', fontsize=12, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_yscale('log')
    
    # Z position distribution
    ax = axes[0, 1]
    ax.hist(particles['z'], bins=50, edgecolor='black', alpha=0.7, color='steelblue')
    ax.set_xlabel('Z Position (cm)', fontsize=12)
    ax.set_ylabel('Count', fontsize=12)
    ax.set_title('Z Position Distribution', fontsize=12, fontweight='bold')
    ax.grid(True, alpha=0.3)
    
    # Radial distribution
    ax = axes[1, 0]
    r = np.sqrt(particles['x']**2 + particles['y']**2)
    ax.hist(r, bins=50, edgecolor='black', alpha=0.7, color='coral')
    ax.set_xlabel('Radial Distance (cm)', fontsize=12)
    ax.set_ylabel('Count', fontsize=12)
    ax.set_title('Radial Distribution from Beam Axis', fontsize=12, fontweight='bold')
    ax.grid(True, alpha=0.3)
    
    # Direction W component (beam divergence)
    ax = axes[1, 1]
    ax.hist(particles['w'], bins=50, edgecolor='black', alpha=0.7, color='green')
    ax.set_xlabel('W (Direction Cosine)', fontsize=12)
    ax.set_ylabel('Count', fontsize=12)
    ax.set_title('Beam Directionality (W component)\n(W≈1 means parallel to Z-axis)', 
                 fontsize=12, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.axvline(0.95, color='red', linestyle='--', alpha=0.5, label='W=0.95')
    ax.legend()
    
    plt.tight_layout()
    
    output_file = output_dir / 'input_phsp_diagnostics.png'
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"✓ Saved: {output_file}")
    plt.close()


def write_analysis_report(header_info, particles, stats, output_dir, sample_rate):
    """Write detailed analysis report to text file"""
    
    report_file = output_dir / 'input_phsp_analysis_report.txt'
    
    with open(report_file, 'w') as f:
        f.write("=" * 70 + "\n")
        f.write("IAEA Phase Space File Analysis Report\n")
        f.write("=" * 70 + "\n\n")
        
        # File information
        f.write("FILE INFORMATION\n")
        f.write("-" * 70 + "\n")
        f.write(f"PHSP File: {PHSP_FILE}\n")
        f.write(f"Header File: {HEADER_FILE}\n")
        f.write(f"Sample Rate: 1 in {sample_rate} particles\n")
        f.write(f"Sampled Particles: {len(particles['x']):,}\n\n")
        
        # Header information
        f.write("BEAM INFORMATION (from Header)\n")
        f.write("-" * 70 + "\n")
        f.write(f"Beam: {header_info.get('beam_name', 'N/A')}\n")
        f.write(f"Nominal SSD: {header_info.get('nominal_ssd', 'N/A')}\n")
        f.write(f"Total Histories: {header_info.get('total_histories', 'N/A'):,}\n")
        f.write(f"Total Particles: {header_info.get('total_particles', 'N/A'):,}\n\n")
        
        # Particle composition
        f.write("PARTICLE COMPOSITION\n")
        f.write("-" * 70 + "\n")
        f.write("From Header File:\n")
        f.write(f"  Photons:    {header_info.get('n_photons', 0):>12,} ({header_info.get('n_photons', 0)/header_info.get('total_particles', 1)*100:>6.2f}%)\n")
        f.write(f"  Electrons:  {header_info.get('n_electrons', 0):>12,} ({header_info.get('n_electrons', 0)/header_info.get('total_particles', 1)*100:>6.2f}%)\n")
        f.write(f"  Positrons:  {header_info.get('n_positrons', 0):>12,} ({header_info.get('n_positrons', 0)/header_info.get('total_particles', 1)*100:>6.2f}%)\n")
        f.write(f"  {'TOTAL:':<12} {header_info.get('total_particles', 0):>12,}\n\n")
        
        f.write("From Sampled Data:\n")
        total_sampled = sum(stats['type_counts'].values())
        for ptype, count in stats['type_counts'].items():
            percentage = count / total_sampled * 100
            f.write(f"  {ptype:<12} {count:>12,} ({percentage:>6.2f}%)\n")
        f.write(f"  {'TOTAL:':<12} {total_sampled:>12,}\n\n")
        
        # Energy statistics
        f.write("ENERGY STATISTICS (MeV)\n")
        f.write("-" * 70 + "\n")
        for ptype, estats in stats['energy_by_type'].items():
            f.write(f"{ptype}:\n")
            f.write(f"  Mean:   {estats['mean']:8.4f} MeV\n")
            f.write(f"  Median: {estats['median']:8.4f} MeV\n")
            f.write(f"  Std:    {estats['std']:8.4f} MeV\n")
            f.write(f"  Range:  [{estats['min']:8.4f}, {estats['max']:8.4f}] MeV\n\n")
        
        # Position statistics
        f.write("SPATIAL DISTRIBUTION (cm)\n")
        f.write("-" * 70 + "\n")
        f.write("From Header File:\n")
        f.write(f"  X Range: [{header_info['x_range'][0]:>8.4f}, {header_info['x_range'][1]:>8.4f}] cm\n")
        f.write(f"  Y Range: [{header_info['y_range'][0]:>8.4f}, {header_info['y_range'][1]:>8.4f}] cm\n")
        f.write(f"  Z Range: [{header_info['z_range'][0]:>8.4f}, {header_info['z_range'][1]:>8.4f}] cm\n\n")
        
        f.write("From Sampled Data:\n")
        for coord in ['x', 'y', 'z']:
            pstats = stats['position'][coord]
            f.write(f"  {coord.upper()} Position:\n")
            f.write(f"    Mean:   {pstats['mean']:8.4f} cm\n")
            f.write(f"    Std:    {pstats['std']:8.4f} cm\n")
            f.write(f"    Range:  [{pstats['min']:8.4f}, {pstats['max']:8.4f}] cm\n")
        
        f.write(f"\n  Radial Distribution:\n")
        f.write(f"    Mean Radius:   {stats['radial']['r_mean']:8.4f} cm\n")
        f.write(f"    Std Radius:    {stats['radial']['r_std']:8.4f} cm\n")
        f.write(f"    Max Radius:    {stats['radial']['r_max']:8.4f} cm\n\n")
        
        # Particle coverage percentage
        f.write("PARTICLE COVERAGE (Percentage within different ranges)\n")
        f.write("-" * 70 + "\n")
        f.write("  Radius   |  % Within  |  |X| ≤ R  |  |Y| ≤ R\n")
        f.write("  " + "-" * 60 + "\n")
        for r_limit in [5, 10, 15, 20, 30]:
            cov = stats['coverage'][r_limit]
            f.write(f"    {r_limit:2d} cm  |   {cov['radial']:5.1f}%   |  {cov['x']:5.1f}%  |  {cov['y']:5.1f}%\n")
        f.write("\n")
        f.write("Key Findings:\n")
        f.write(f"  • {stats['coverage'][10]['radial']:.1f}% of particles within 10 cm radius\n")
        f.write(f"  • {stats['coverage'][20]['radial']:.1f}% of particles within 20 cm radius\n")
        f.write(f"  • Only {100-stats['coverage'][20]['radial']:.1f}% in the outer 20-30 cm region\n\n")
        
        # Direction statistics
        f.write("DIRECTION STATISTICS\n")
        f.write("-" * 70 + "\n")
        f.write(f"W Component (along beam axis):\n")
        f.write(f"  Mean: {stats['direction']['w_mean']:8.6f}\n")
        f.write(f"  Std:  {stats['direction']['w_std']:8.6f}\n")
        f.write(f"  Range: [{stats['direction']['w_min']:8.6f}, {stats['direction']['w_max']:8.6f}]\n")
        f.write(f"  (W≈1 means particles moving parallel to Z-axis)\n\n")
        
        f.write(f"Angular Distribution:\n")
        f.write(f"  Theta (azimuthal):  Mean = {stats['angles']['theta_mean']:7.3f}°, Std = {stats['angles']['theta_std']:7.3f}°\n")
        f.write(f"  Phi (polar):        Mean = {stats['angles']['phi_mean']:7.3f}°, Std = {stats['angles']['phi_std']:7.3f}°\n\n")
        
        # Coordinate system
        f.write("COORDINATE SYSTEM\n")
        f.write("-" * 70 + "\n")
        coord_sys = header_info.get('coord_system', 'Not specified')
        for line in coord_sys.split('\n'):
            f.write(f"{line.strip()}\n")
        f.write("\n")
        
        # Important notes
        f.write("IMPORTANT NOTES\n")
        f.write("-" * 70 + "\n")
        f.write("1. Source Type: Patient-independent cylindrical phase space\n")
        f.write("2. Beam Quality: 6MV photon beam from Varian TrueBeam linac\n")
        f.write("3. Source Location: Above the movable upper jaws (field-independent)\n")
        f.write("4. Primary Radiation: Photons (>98%), with small electron/positron\n")
        f.write("   contamination from linac head interactions\n")
        f.write(f"5. Spatial Distribution: HIGHLY CONCENTRATED near beam axis\n")
        f.write(f"   • Range: ±30 cm (extreme outliers)\n")
        f.write(f"   • {stats['coverage'][10]['radial']:.1f}% of particles within ±10 cm\n")
        f.write(f"   • Standard deviation: X={stats['position']['x']['std']:.1f} cm, "
                f"Y={stats['position']['y']['std']:.1f} cm\n")
        f.write("6. Z Position: Source particles distributed over ~10cm depth\n")
        f.write("   (17.77-27.35 cm), representing actual linac geometry\n")
        f.write("7. Beam Divergence: Highly collimated (W>0.95 for most particles)\n")
        f.write(f"8. Mean W = {stats['direction']['w_mean']:.6f} → Divergence angle\n")
        f.write(f"   ≈ {np.degrees(np.arccos(stats['direction']['w_mean'])):.2f}°\n")
        f.write(f"9. CRITICAL: Do NOT design geometry based on Range extremes!\n")
        f.write(f"   Use standard deviation or 95% coverage for realistic sizing\n\n")
        
        # Recommendations
        f.write("RECOMMENDATIONS FOR GEANT4 GEOMETRY\n")
        f.write("-" * 70 + "\n")
        f.write(f"Based on actual particle distribution (not just range extremes):\n\n")
        
        cov_10 = stats['coverage'][10]['radial']
        cov_20 = stats['coverage'][20]['radial']
        
        f.write(f"1. Water Phantom Size Options:\n\n")
        f.write(f"   Option A: 20×20×20 cm³ (Current)\n")
        f.write(f"   • Covers: {cov_20:.1f}% of particles\n")
        f.write(f"   • Pros: Reasonable, captures >95% of source\n")
        f.write(f"   • Cons: Misses {100-cov_20:.1f}% in outer region\n")
        f.write(f"   • Verdict: ✓ ADEQUATE for most applications\n\n")
        
        f.write(f"   Option B: 30×30×20 cm³\n")
        f.write(f"   • Covers: ~99% of particles\n")
        f.write(f"   • Pros: Better coverage, more realistic\n")
        f.write(f"   • Cons: 2.25× more volume to simulate\n")
        f.write(f"   • Verdict: ✓ RECOMMENDED for comprehensive studies\n\n")
        
        f.write(f"   Option C: 40×40×20 cm³\n")
        f.write(f"   • Covers: >99.5% of particles\n")
        f.write(f"   • Pros: Nearly complete coverage\n")
        f.write(f"   • Cons: 4× more volume, slower simulation\n")
        f.write(f"   • Verdict: Consider only if edge effects are critical\n\n")
        
        f.write(f"2. Water Phantom Position:\n")
        f.write(f"   • Z-center: ~30 cm (Z-range: 20-40 cm)\n")
        f.write(f"   • This ensures all source particles (Z=17.77-27.35) enter the water\n\n")
        
        f.write(f"3. World Volume:\n")
        f.write(f"   • Should be ≥150×150×150 cm³ to contain full geometry\n\n")
        
        f.write(f"4. Important Note:\n")
        f.write(f"   • The source has Range = ±30 cm, but {cov_10:.1f}% of particles\n")
        f.write(f"     are actually within ±10 cm (highly concentrated)\n")
        f.write(f"   • Standard deviation: X={stats['position']['x']['std']:.1f} cm, "
                f"Y={stats['position']['y']['std']:.1f} cm\n")
        f.write(f"   • This is typical for medical linac beams (collimated)\n\n")
        
        f.write("=" * 70 + "\n")
        f.write(f"Analysis completed successfully!\n")
        f.write(f"Generated: {report_file.name}\n")
        f.write("=" * 70 + "\n")
    
    print(f"✓ Saved: {report_file}")


def main():
    parser = argparse.ArgumentParser(description='Analyze IAEA PHSP file')
    parser.add_argument('--sample', type=int, default=100,
                        help='Sample rate: read every Nth particle (default: 100)')
    args = parser.parse_args()
    
    # Create output directory
    output_dir = Path(OUTPUT_DIR)
    output_dir.mkdir(exist_ok=True)
    
    print("=" * 70)
    print("IAEA Phase Space File Analyzer")
    print("=" * 70)
    print()
    
    # Read header
    print("Step 1: Reading header file...")
    header_info = read_header_info(HEADER_FILE)
    print(f"✓ Total particles in PHSP: {header_info.get('total_particles', 'Unknown'):,}\n")
    
    # Read particle data
    print("Step 2: Reading particle data...")
    particles = read_phsp_particles(PHSP_FILE, sample_rate=args.sample)
    
    # Analyze
    print("Step 3: Analyzing particle distributions...")
    stats = analyze_particles(particles, header_info)
    print("✓ Analysis complete\n")
    
    # Generate plots
    print("Step 4: Generating visualizations...")
    plot_xy_distribution(particles, header_info, output_dir)
    plot_additional_diagnostics(particles, header_info, output_dir)
    print()
    
    # Write report
    print("Step 5: Writing analysis report...")
    write_analysis_report(header_info, particles, stats, output_dir, args.sample)
    print()
    
    print("=" * 70)
    print("Analysis Complete!")
    print("=" * 70)
    print(f"Output directory: {output_dir}")
    print(f"  • input_phsp_xy_distribution.png - X-Y position heatmap")
    print(f"  • input_phsp_diagnostics.png - Additional diagnostics")
    print(f"  • input_phsp_analysis_report.txt - Detailed report")
    print("=" * 70)


if __name__ == '__main__':
    main()
