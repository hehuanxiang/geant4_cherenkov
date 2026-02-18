//
// RunMetadata.hh
// 负责为每次模拟 Run 写出一个 JSON 元数据文件，便于后处理和追踪
//

#ifndef RunMetadata_h
#define RunMetadata_h 1

#include <string>

class G4Run;

namespace RunMetadata {

// 写出运行元数据到指定路径（通常是 fOutputBasePath + ".run_meta.json"）
// 仅在 master 线程、EndOfRunAction 中调用
void Write(const std::string& metaPath,
           const G4Run* run,
           const std::string& outputBasePath,
           const std::string& outputFormat,
           long wallSeconds,
           long cpuSeconds,
           long totalPhotons,
           int numThreads,
           long totalDeposits = 0,
           const std::string& doseOutputBasePath = "",
           long doseDepositsWithoutPrimary = 0);

}  // namespace RunMetadata

#endif

