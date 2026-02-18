#!/bin/bash
# Run script for Cherenkov simulation with proper GEANT4 environment

# Resolve project root (two levels up from this script)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Source GEANT4 environment
source /home/xhh2c/Applications/GEANT4/geant4-install/bin/geant4.sh

# Set GEANT4 data paths
export G4NEUTRONHPDATA=/home/xhh2c/Applications/GEANT4/G4DATA/G4NDL4.7.1
export G4LEDATA=/home/xhh2c/Applications/GEANT4/G4DATA/G4EMLOW8.6.1
export G4LEVELGAMMADATA=/home/xhh2c/Applications/GEANT4/G4DATA/PhotonEvaporation6.1
export G4RADIOACTIVEDATA=/home/xhh2c/Applications/GEANT4/G4DATA/RadioactiveDecay6.1.2
export G4PARTICLEXSDATA=/home/xhh2c/Applications/GEANT4/G4DATA/G4PARTICLEXS4.1
export G4PIIDATA=/home/xhh2c/Applications/GEANT4/G4DATA/G4PII1.3
export G4REALSURFACEDATA=/home/xhh2c/Applications/GEANT4/G4DATA/RealSurface2.2
export G4SAIDXSDATA=/home/xhh2c/Applications/GEANT4/G4DATA/G4SAIDDATA2.0
export G4ABLADATA=/home/xhh2c/Applications/GEANT4/G4DATA/G4ABLA3.3
export G4INCLDATA=/home/xhh2c/Applications/GEANT4/G4DATA/G4INCL1.2
export G4ENSDFSTATEDATA=/home/xhh2c/Applications/GEANT4/G4DATA/G4ENSDFSTATE3.0
export G4TENDLDATA=/home/xhh2c/Applications/GEANT4/G4DATA/G4TENDL1.4

echo "GEANT4 environment configured"
echo "Running Cherenkov simulation..."

cd "$PROJECT_ROOT/build"

# Create output directory if it doesn't exist
mkdir -p "$PROJECT_ROOT/output"

# Create log directory if it doesn't exist
LOG_DIR="$PROJECT_ROOT/log"
mkdir -p "$LOG_DIR"

# Copy/Link config.json to build directory for easy access
if [ ! -L config.json ]; then
  ln -sf ../config.json config.json
fi

# Generate log filename with timestamp
LOG_FILE="$LOG_DIR/simulation_$(date +%Y%m%d_%H%M%S).log"

# Log message header
{
  echo "==============================================="
  echo "Cherenkov Simulation Log"
  echo "Start time: $(date)"
  echo "Config file: $(pwd)/config.json"
  echo "==============================================="
  echo ""
} | tee "$LOG_FILE"

if [ "$1" == "test" ]; then
  echo "Running test configuration (100 events, via --mode test)..." | tee -a "$LOG_FILE"
  
  # Read output_format from config.json to determine file extension
  OUTPUT_FORMAT=$(python3 -c "import json; config = json.load(open('../config.json')); print(config.get('simulation', {}).get('output_format', 'binary'))" 2>/dev/null || echo "binary")
  if [ "$OUTPUT_FORMAT" == "csv" ]; then
    OUTPUT_EXT="csv"
  else
    OUTPUT_EXT="phsp"
  fi
  
  # Read output_file_path from config.json (respect user's setting)
  OUTPUT_BASE=$(python3 -c "import json; config = json.load(open('../config.json')); print(config.get('simulation', {}).get('output_file_path', '${PROJECT_ROOT}/output/cherenkov_photons_test').strip())" 2>/dev/null || echo "${PROJECT_ROOT}/output/cherenkov_photons_test")
  OUTPUT_FILE="${OUTPUT_BASE}.${OUTPUT_EXT}"
  echo "Output format: $OUTPUT_FORMAT | Output file: $OUTPUT_FILE" | tee -a "$LOG_FILE"
  ./CherenkovSim --config ../config.json --mode test --macro ../macros/run_base.mac 2>&1 | tee -a "$LOG_FILE"
elif [ "$1" == "full" ]; then
  echo "Running full simulation (52,302,569 events - complete PHSP, via --mode full)..." | tee -a "$LOG_FILE"
  
  # Read output_format from config.json to determine file extension
  OUTPUT_FORMAT=$(python3 -c "import json; config = json.load(open('../config.json')); print(config.get('simulation', {}).get('output_format', 'binary'))" 2>/dev/null || echo "binary")
  if [ "$OUTPUT_FORMAT" == "csv" ]; then
    OUTPUT_EXT="csv"
  else
    OUTPUT_EXT="phsp"
  fi
  
  # Read output_file_path from config.json (respect user's setting)
  OUTPUT_BASE=$(python3 -c "import json; config = json.load(open('../config.json')); print(config.get('simulation', {}).get('output_file_path', '${PROJECT_ROOT}/output/cherenkov_photons_full').strip())" 2>/dev/null || echo "${PROJECT_ROOT}/output/cherenkov_photons_full")
  OUTPUT_FILE="${OUTPUT_BASE}.${OUTPUT_EXT}"
  echo "Output format: $OUTPUT_FORMAT | Output file: $OUTPUT_FILE" | tee -a "$LOG_FILE"
  ./CherenkovSim --config ../config.json --mode full --macro ../macros/run_base.mac 2>&1 | tee -a "$LOG_FILE"
elif [ -z "$1" ]; then
  echo "Usage: $0 [test|full|<macro_file>] [--config <config_file>]" | tee -a "$LOG_FILE"
  echo "  test                            - Run 100 events (quick test, via --mode test)" | tee -a "$LOG_FILE"
  echo "  full                            - Run 52,302,569 events (complete PHSP, via --mode full)" | tee -a "$LOG_FILE"
  echo "  <macro_file>                    - Run with custom macro file" | tee -a "$LOG_FILE"
  echo "  --config <config_file>          - Use custom config file (optional)" | tee -a "$LOG_FILE"
  echo "" | tee -a "$LOG_FILE"
  echo "Examples:" | tee -a "$LOG_FILE"
  echo "  bash scripts/run_simulation.sh test" | tee -a "$LOG_FILE"
  echo "  bash scripts/run_simulation.sh run.mac --config my_config.json" | tee -a "$LOG_FILE"
else
  # Check if second argument is --config
  if [ "$2" == "--config" ] && [ -n "$3" ]; then
    echo "Running custom macro: $1 with config: $3" | tee -a "$LOG_FILE"
    ./CherenkovSim --config "$3" "$1" 2>&1 | tee -a "$LOG_FILE"
  else
    echo "Running custom macro: $1" | tee -a "$LOG_FILE"
    ./CherenkovSim --config ../config.json "$1" 2>&1 | tee -a "$LOG_FILE"
  fi
fi

# Log footer
{
  echo ""
  echo "==============================================="
  echo "Simulation ended"
  echo "End time: $(date)"
  echo "Log saved to: $LOG_FILE"
  echo "==============================================="
} | tee -a "$LOG_FILE"

