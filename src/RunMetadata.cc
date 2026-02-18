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
           int numThreads)
{
  std::ofstream out(metaPath);
  if (!out.is_open()) {
    // 元数据写入失败不应影响主模拟，直接返回即可
    return;
  }

  // 获取当前时间（写入时间戳）
  std::time_t now = std::time(nullptr);
  char timeBuf[64];
  if (std::strftime(timeBuf, sizeof(timeBuf), "%Y-%m-%dT%H:%M:%S", std::localtime(&now)) == 0) {
    timeBuf[0] = '\0';
  }

  // 从 Config 中取部分配置（若可用）
  Config* config = Config::GetInstance();
  std::string phspPath = "";
  std::string configPath = "";  // 无直接记录，用户可在日志中查看；这里占位
  int cfgThreads = 0;
  if (config) {
    phspPath = config->GetPHSPFilePath();
    cfgThreads = config->GetNumThreads();
  }

  long events = run ? run->GetNumberOfEvent() : 0;

  // 手写一个简单 JSON，便于 Python/其他工具解析
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
  out << "  \"wall_time_seconds\": " << wallSeconds << ",\n";
  out << "  \"cpu_time_seconds\": " << cpuSeconds << "\n";
  out << "}\n";

  out.close();
}

}  // namespace RunMetadata

