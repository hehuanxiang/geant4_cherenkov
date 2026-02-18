#include "Config.hh"
#include <fstream>
#include <iostream>

Config* Config::fInstance = nullptr;

Config::Config()
{
}

Config* Config::GetInstance()
{
  if (fInstance == nullptr) {
    fInstance = new Config();
  }
  return fInstance;
}

void Config::LoadConfig(const std::string& configFilePath)
{
  std::ifstream configFile(configFilePath);
  if (!configFile.is_open()) {
    std::cerr << "ERROR: Cannot open config file: " << configFilePath << std::endl;
    return;
  }
  
  try {
    configFile >> fConfig;
    std::cout << "Config loaded successfully from: " << configFilePath << std::endl;
  } catch (const std::exception& e) {
    std::cerr << "ERROR: Failed to parse config file: " << e.what() << std::endl;
  }
}

// Geometry parameters
double Config::GetWorldSizeX() const
{
  return fConfig["geometry"]["world_size_xyz_cm"][0];
}

double Config::GetWorldSizeY() const
{
  return fConfig["geometry"]["world_size_xyz_cm"][1];
}

double Config::GetWorldSizeZ() const
{
  return fConfig["geometry"]["world_size_xyz_cm"][2];
}

double Config::GetWaterSizeX() const
{
  return fConfig["geometry"]["water_size_xyz_cm"][0];
}

double Config::GetWaterSizeY() const
{
  return fConfig["geometry"]["water_size_xyz_cm"][1];
}

double Config::GetWaterSizeZ() const
{
  return fConfig["geometry"]["water_size_xyz_cm"][2];
}

double Config::GetWaterPositionX() const
{
  return fConfig["geometry"]["water_position_cm"][0];
}

double Config::GetWaterPositionY() const
{
  return fConfig["geometry"]["water_position_cm"][1];
}

double Config::GetWaterPositionZ() const
{
  return fConfig["geometry"]["water_position_cm"][2];
}

std::string Config::GetPhantomVolumeName() const
{
  return fConfig["geometry"]["phantom_volume_name"];
}

bool Config::GetCheckOverlaps() const
{
  return fConfig["geometry"]["check_overlaps"];
}

// Material parameters - Air
double Config::GetAirDensity() const
{
  return fConfig["materials"]["air"]["density_mg_cm3"];
}

double Config::GetAirNitrogenFraction() const
{
  return fConfig["materials"]["air"]["elements"][0]["fraction"];
}

double Config::GetAirOxygenFraction() const
{
  return fConfig["materials"]["air"]["elements"][1]["fraction"];
}

double Config::GetNitrogenAtomicNumber() const
{
  return fConfig["materials"]["air"]["elements"][0]["z"];
}

double Config::GetNitrogenMass() const
{
  return fConfig["materials"]["air"]["elements"][0]["a_g_mol"];
}

double Config::GetOxygenAtomicNumber() const
{
  return fConfig["materials"]["air"]["elements"][1]["z"];
}

double Config::GetOxygenMass() const
{
  return fConfig["materials"]["air"]["elements"][1]["a_g_mol"];
}

// Material parameters - Water
double Config::GetWaterDensity() const
{
  return fConfig["materials"]["water"]["density_g_cm3"];
}

double Config::GetHydrogenAtomicNumber() const
{
  return fConfig["materials"]["water"]["elements"][0]["z"];
}

double Config::GetHydrogenMass() const
{
  return fConfig["materials"]["water"]["elements"][0]["a_g_mol"];
}

std::vector<double> Config::GetWaterPhotonEnergies() const
{
  return fConfig["materials"]["water"]["optical_properties"]["photon_energy_eV"].get<std::vector<double>>();
}

std::vector<double> Config::GetWaterRefractiveIndices() const
{
  return fConfig["materials"]["water"]["optical_properties"]["refractive_index"].get<std::vector<double>>();
}

std::vector<double> Config::GetWaterAbsorptionLengths() const
{
  return fConfig["materials"]["water"]["optical_properties"]["absorption_length_m"].get<std::vector<double>>();
}

// Optical properties - Air
std::vector<double> Config::GetAirPhotonEnergies() const
{
  return fConfig["materials"]["air_optical_properties"]["photon_energy_eV"].get<std::vector<double>>();
}

double Config::GetAirRefractiveIndex() const
{
  return fConfig["materials"]["air_optical_properties"]["refractive_index"];
}

// Simulation parameters
std::string Config::GetPHSPFilePath() const
{
  return fConfig["simulation"]["phsp_file_path"];
}

std::string Config::GetOutputFilePath() const
{
  return fConfig["simulation"]["output_file_path"];
}

int Config::GetNumThreads() const
{
  return fConfig["simulation"]["num_threads"];
}

std::string Config::GetOutputFormat() const
{
  // Default to binary if not specified
  if (fConfig["simulation"].contains("output_format")) {
    return fConfig["simulation"]["output_format"];
  }
  return "binary";
}

int Config::GetBufferSize() const
{
  // Default buffer size: 100000 photons
  if (fConfig["simulation"].contains("buffer_size")) {
    return fConfig["simulation"]["buffer_size"];
  }
  return 100000;
}

bool Config::GetEnableCherenkovOutput() const
{
  if (fConfig["simulation"].contains("enable_cherenkov_output")) {
    return fConfig["simulation"]["enable_cherenkov_output"].get<bool>();
  }
  return true;
}

bool Config::GetEnableDoseOutput() const
{
  if (fConfig["simulation"].contains("enable_dose_output")) {
    return fConfig["simulation"]["enable_dose_output"].get<bool>();
  }
  return false;
}

std::string Config::GetDoseOutputFilePath() const
{
  if (fConfig["simulation"].contains("dose_output_path")) {
    std::string p = fConfig["simulation"]["dose_output_path"].get<std::string>();
    if (!p.empty()) return p;
  }
  return fConfig["simulation"]["output_file_path"].get<std::string>();
}

int Config::GetDoseBufferSize() const
{
  if (fConfig["simulation"].contains("dose_buffer_size")) {
    return fConfig["simulation"]["dose_buffer_size"].get<int>();
  }
  return GetBufferSize();
}
