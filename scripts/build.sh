#!/bin/bash
# Build script for Cherenkov simulation

# Resolve project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "Building GEANT4 Cherenkov Simulation..."

# Ensure Geant4 data path exists for geant4.sh
G4DATA_DIR="/home/xhh2c/Applications/GEANT4/G4DATA"
G4_SHARE_DIR="/home/xhh2c/Applications/GEANT4/geant4-install/share/Geant4"
G4_DATA_LINK="$G4_SHARE_DIR/data"
if [ ! -e "$G4_DATA_LINK" ]; then
  mkdir -p "$G4_SHARE_DIR"
  ln -s "$G4DATA_DIR" "$G4_DATA_LINK"
fi

# Source GEANT4 environment
if [ -f /home/xhh2c/Applications/GEANT4/geant4-install/bin/geant4.sh ]; then
  # shellcheck source=/dev/null
  source /home/xhh2c/Applications/GEANT4/geant4-install/bin/geant4.sh
  echo "GEANT4 environment sourced"
else
  echo "Warning: Could not find GEANT4 configuration script"
fi

# Set Geant4 directory for CMake
export Geant4_DIR=/home/xhh2c/Applications/GEANT4/geant4-install/lib/cmake/Geant4

# Create build directory
cd "$PROJECT_ROOT"
if [ ! -d "build" ]; then
  mkdir -p build
fi

cd build

# Configure and build
cmake .. && make -j8

if [ $? -eq 0 ]; then
  echo ""
  echo "Build successful!"
  echo ""
  echo "CONFIGURATION:"
  echo "  Edit parameters in: ../config.json"
  echo "  - Geometry: world and water sizes, positions"
  echo "  - Materials: air and water properties, optical parameters"
  echo "  - Simulation: PHSP file path, output file path, thread count"
  echo ""
  echo "To run the simulation using run_simulation.sh:"
  echo "  bash ../scripts/run_simulation.sh test                                 # Quick test (100 events)"
  echo "  bash ../scripts/run_simulation.sh full                                 # Full run (complete PHSP)"
  echo "  bash ../scripts/run_simulation.sh <macro> --config <config_file>       # Custom macro + config"
  echo ""
  echo "Or run directly with command-line config specification:"
  echo "  cd build"
  echo "  ln -sf ../config.json config.json                  # Link default config"
  echo "  ./CherenkovSim --config ../config.json --mode full --macro ../macros/run_base.mac"
  echo "  ./CherenkovSim                                      # Interactive mode (default config)"
  echo ""
  echo "Output will be saved to: path specified in config.json"
  echo "Logs will be saved to: log/simulation_YYYYMMDD_HHMMSS.log"
else
  echo "Build failed!"
  exit 1
fi

