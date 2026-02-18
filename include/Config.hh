#ifndef CONFIG_HH
#define CONFIG_HH

#include <string>
#include <vector>
#include <nlohmann/json.hpp>

using json = nlohmann::json;

class Config {
private:
  static Config* fInstance;
  json fConfig;
  
  // Private constructor
  Config();
  
public:
  // Singleton pattern
  static Config* GetInstance();
  
  // Load config from JSON file
  void LoadConfig(const std::string& configFilePath);
  
  // Geometry parameters
  double GetWorldSizeX() const;
  double GetWorldSizeY() const;
  double GetWorldSizeZ() const;
  double GetWaterSizeX() const;
  double GetWaterSizeY() const;
  double GetWaterSizeZ() const;
  double GetWaterPositionX() const;
  double GetWaterPositionY() const;
  double GetWaterPositionZ() const;
  std::string GetPhantomVolumeName() const;
  bool GetCheckOverlaps() const;
  
  // Material parameters - Air
  double GetAirDensity() const;
  double GetAirNitrogenFraction() const;
  double GetAirOxygenFraction() const;
  double GetNitrogenAtomicNumber() const;
  double GetNitrogenMass() const;
  double GetOxygenAtomicNumber() const;
  double GetOxygenMass() const;
  
  // Material parameters - Water
  double GetWaterDensity() const;
  double GetHydrogenAtomicNumber() const;
  double GetHydrogenMass() const;
  std::vector<double> GetWaterPhotonEnergies() const;
  std::vector<double> GetWaterRefractiveIndices() const;
  std::vector<double> GetWaterAbsorptionLengths() const;
  
  // Optical properties - Air
  std::vector<double> GetAirPhotonEnergies() const;
  double GetAirRefractiveIndex() const;
  
  // Simulation parameters
  std::string GetPHSPFilePath() const;
  std::string GetOutputFilePath() const;
  int GetNumThreads() const;
  
  // Output format: "csv" or "binary"
  std::string GetOutputFormat() const;
  int GetBufferSize() const;

  // Cherenkov / Dose output switches (use contains() + defaults)
  bool GetEnableCherenkovOutput() const;
  bool GetEnableDoseOutput() const;
  std::string GetDoseOutputFilePath() const;  // base path for .dose; if empty use output_file_path
  int GetDoseBufferSize() const;
};

#endif // CONFIG_HH
