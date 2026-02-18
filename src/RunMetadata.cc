//
// RunMetadata.cc
//

#include "RunMetadata.hh"

#include "G4Run.hh"
#include "Config.hh"

#include <fstream>
#include <iomanip>
#include <ctime>

namespace RunMetadata {

void Write(const std::string& metaPath,
           const G4Run* run,
           const std::string& outputBasePath,
           const std::string& outputFormat,
           long wallSeconds,
           long cpuSeconds,
           long totalPhotons,
           int numThreads,
           long totalDeposits,
           const std::string& doseOutputBasePath,
           long doseDepositsWithoutPrimary)
{
  std::ofstream out(metaPath);
  if (!out.is_open()) {
    return;
  }

  std::time_t now = std::time(nullptr);
  char timeBuf[64];
  if (std::strftime(timeBuf, sizeof(timeBuf), "%Y-%m-%dT%H:%M:%S", std::localtime(&now)) == 0) {
    timeBuf[0] = '\0';
  }

  Config* config = Config::GetInstance();
  std::string phspPath = "";
  std::string configPath = "";
  int cfgThreads = 0;
  if (config) {
    phspPath = config->GetPHSPFilePath();
    cfgThreads = config->GetNumThreads();
  }

  long events = run ? run->GetNumberOfEvent() : 0;

  out << "{\n";
  out << "  \"timestamp\": \"" << timeBuf << "\",\n";
  out << "  \"output_base_path\": \"" << outputBasePath << "\",\n";
  out << "  \"output_format\": \"" << outputFormat << "\",\n";
  out << "  \"phsp_file_path\": \"" << phspPath << "\",\n";
  out << "  \"config_file_path_hint\": \"" << configPath << "\",\n";
  out << "  \"num_threads_config\": " << cfgThreads << ",\n";
  out << "  \"num_threads_effective\": " << numThreads << ",\n";
  out << "  \"events\": " << events << ",\n";
  out << "  \"total_photons\": " << totalPhotons << ",\n";
  if (!doseOutputBasePath.empty()) {
    out << "  \"total_deposits\": " << totalDeposits << ",\n";
    out << "  \"dose_output_path\": \"" << doseOutputBasePath << ".dose\",\n";
    out << "  \"dose_deposits_without_primary\": " << doseDepositsWithoutPrimary << ",\n";
  }
  out << "  \"wall_time_seconds\": " << wallSeconds << ",\n";
  out << "  \"cpu_time_seconds\": " << cpuSeconds << "\n";
  out << "}\n";

  out.close();
}

}  // namespace RunMetadata

