#!/bin/bash
# Run Cherenkov kernel and dose kernel build after full simulation has completed.
# Uses output path from config.json (same as run_simulation.sh full).

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# Read output base from config (same as run_simulation.sh)
OUTPUT_BASE=$(python3 -c "
import json
with open('config.json') as f:
    c = json.load(f)
print(c.get('simulation', {}).get('output_file_path', 'output/cherenkov_photons_full').strip())
" 2>/dev/null || echo "output/cherenkov_photons_full")

PHSP="${OUTPUT_BASE}.phsp"
DOSE="${OUTPUT_BASE}.dose"
CHERN_OUT="${PROJECT_ROOT}/kernel_output"
DOSE_OUT="${PROJECT_ROOT}/dose_kernel_output"

# ---- Cherenkov kernel ----
if [ ! -f "$PHSP" ]; then
  echo "ERROR: PHSP file not found: $PHSP"
  echo "Run full simulation first: bash scripts/run_simulation.sh full"
  exit 1
fi

echo "=== Cherenkov kernel ==="
echo "PHSP: $PHSP"
echo "Output dir: $CHERN_OUT"
python3 analysis/build_cherenkov_kernel.py \
  --phsp "$PHSP" \
  --config config.json \
  --output-dir "$CHERN_OUT"
echo "Cherenkov kernel done: $CHERN_OUT"

# ---- Dose kernel (if .dose exists) ----
if [ -f "$DOSE" ]; then
  echo ""
  echo "=== Dose kernel ==="
  echo "Dose: $DOSE"
  echo "Output dir: $DOSE_OUT"
  python3 analysis/build_dose_kernel.py \
    --dose "$DOSE" \
    --config config.json \
    --output-dir "$DOSE_OUT"
  echo "Dose kernel done: $DOSE_OUT"
else
  echo ""
  echo "No .dose file at $DOSE (enable_dose_output may be false). Skipping dose kernel."
fi

echo ""
echo "Done. Cherenkov kernel: $CHERN_OUT"
echo "      Dose kernel:      $DOSE_OUT (if generated)"
