#!/usr/bin/env python3
"""
Cherenkov Photon Analysis - Modularized Version
Clean architecture with separate data loading and plotting functions

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

# ============= Configuration =============
BINARY_FILE = '/home/xhh2c/project/geant4_cherenkov/output/cherenkov_photons_full.phsp'
OUTPUT_DIR = '/home/xhh2c/project/geant4_cherenkov/plot'
SAMPLE_RATE = 10

os.makedirs(OUTPUT_DIR, exist_ok=True)
plt.style.use('seaborn-v0_8-whitegrid')
sns.set_palette("husl")

# 下面内容与原 analyze_cherenkov_fast.py 保持一致
@@
