//
// RunAction.cc
//

#include "RunAction.hh"
#include "EventAction.hh"
#include "RunMetadata.hh"

#include "G4Run.hh"
#include "G4RunManager.hh"
#include "G4SystemOfUnits.hh"
#include "G4Threading.hh"
#include "Config.hh"
#ifdef G4MULTITHREADED
#include "G4MTRunManager.hh"
#endif
#include <iostream>
#include <iomanip>
#include <sstream>
#include <fstream>
#include <algorithm>
#include <cstdio>
#include <cerrno>
#include <cstring>

// Define static class members
thread_local std::ofstream RunAction::fThreadOutputStream;
std::string RunAction::fOutputBasePath = "";
thread_local PhotonBuffer* RunAction::fThreadBuffer = nullptr;
PhotonBuffer* RunAction::fMasterBuffer = nullptr;
thread_local DoseBuffer* RunAction::fThreadDoseBuffer = nullptr;
DoseBuffer* RunAction::fMasterDoseBuffer = nullptr;

// 定义构造函数和析构函数
RunAction::RunAction()
: G4UserRunAction(), fOutputFormat("binary")
{ 
}

RunAction::~RunAction()
{
  // Close thread-local file if open (CSV mode)
  if (fThreadOutputStream.is_open()) {
    fThreadOutputStream.close();
  }
  
  // Delete thread-local buffer if exists (Binary mode)
  if (fThreadBuffer != nullptr) {
    delete fThreadBuffer;
    fThreadBuffer = nullptr;
  }
  
  // Delete master buffer (only master thread in MT; always in sequential)
#ifdef G4MULTITHREADED
  if (G4Threading::IsMasterThread() && fMasterBuffer != nullptr) {
    delete fMasterBuffer;
    fMasterBuffer = nullptr;
  }
#else
  if (fMasterBuffer != nullptr) {
    delete fMasterBuffer;
    fMasterBuffer = nullptr;
  }
#endif

  if (fThreadDoseBuffer != nullptr) {
    delete fThreadDoseBuffer;
    fThreadDoseBuffer = nullptr;
  }
#ifdef G4MULTITHREADED
  if (G4Threading::IsMasterThread() && fMasterDoseBuffer != nullptr) {
    delete fMasterDoseBuffer;
    fMasterDoseBuffer = nullptr;
  }
#else
  if (fMasterDoseBuffer != nullptr) {
    delete fMasterDoseBuffer;
    fMasterDoseBuffer = nullptr;
  }
#endif
}

void RunAction::BeginOfRunAction(const G4Run*)
{ 
  // 记录开始时间和CPU时间
  fStartTime = std::chrono::high_resolution_clock::now();
  getrusage(RUSAGE_SELF, &fStartUsage);
  
  // 重置光子计数（仅 master 执行，避免 MT 下并发写）
#ifdef G4MULTITHREADED
  if (G4Threading::IsMasterThread())
#endif
  {
    EventAction::ResetPhotonCount();
    EventAction::ResetDoseDepositsWithoutPrimary();
  }

  Config* config = Config::GetInstance();
  std::string outputFilePath = config->GetOutputFilePath();
#ifdef G4MULTITHREADED
  if (G4Threading::IsMasterThread())
#endif
  {
    fOutputBasePath = outputFilePath;
  }
  fOutputFormat = config->GetOutputFormat();
  std::transform(fOutputFormat.begin(), fOutputFormat.end(), fOutputFormat.begin(), ::tolower);

  G4cout << "Output format: " << fOutputFormat << G4endl;

  if (fOutputFormat == "binary") {
    G4int bufferSize = config->GetBufferSize();

    if (config->GetEnableCherenkovOutput()) {
#ifdef G4MULTITHREADED
      if (G4Threading::IsWorkerThread()) {
        fThreadBuffer = new PhotonBuffer(bufferSize);
        G4cout << "Worker thread " << G4Threading::G4GetThreadId()
               << " buffer size: " << fThreadBuffer->GetBufferSize() << G4endl;
      } else {
        // Remove existing file (if any) and create new one
        std::string phspPath = fOutputBasePath + ".phsp";
        if (std::remove(phspPath.c_str()) != 0 && errno != ENOENT) {
          // ENOENT means file doesn't exist, which is fine
          // Other errors might indicate permission issues or file in use
          G4cerr << "WARNING: Cannot remove existing file: " << phspPath << G4endl;
          G4cerr << "         Error: " << std::strerror(errno) << G4endl;
          G4cerr << "         Will attempt to truncate instead..." << G4endl;
        }
        std::ofstream truncateFile(phspPath, std::ios::out | std::ios::trunc | std::ios::binary);
        if (!truncateFile.good()) {
          G4cerr << "ERROR: Cannot create output file: " << phspPath << G4endl;
          G4cerr << "       Error: " << std::strerror(errno) << G4endl;
          G4cerr << "       Please check file permissions and ensure no other process is using it." << G4endl;
          return;
        }
        truncateFile.close();
        if (fMasterBuffer == nullptr) {
          fMasterBuffer = new PhotonBuffer(bufferSize);
          fMasterBuffer->SetOutputPath(phspPath);
          G4cout << "Master buffer created with size: " << bufferSize << G4endl;
        }
      }
#else
      // Remove existing file (if any) and create new one
      std::string phspPath = fOutputBasePath + ".phsp";
      if (std::remove(phspPath.c_str()) != 0 && errno != ENOENT) {
        // ENOENT means file doesn't exist, which is fine
        // Other errors might indicate permission issues or file in use
        G4cerr << "WARNING: Cannot remove existing file: " << phspPath << G4endl;
        G4cerr << "         Error: " << std::strerror(errno) << G4endl;
        G4cerr << "         Will attempt to truncate instead..." << G4endl;
      }
      std::ofstream truncateFile(phspPath, std::ios::out | std::ios::trunc | std::ios::binary);
      if (!truncateFile.good()) {
        G4cerr << "ERROR: Cannot create output file: " << phspPath << G4endl;
        G4cerr << "       Error: " << std::strerror(errno) << G4endl;
        G4cerr << "       Please check file permissions and ensure no other process is using it." << G4endl;
        return;
      }
      truncateFile.close();
      if (fMasterBuffer == nullptr) {
        fMasterBuffer = new PhotonBuffer(bufferSize);
        fMasterBuffer->SetOutputPath(phspPath);
      }
#endif
    }

    if (config->GetEnableDoseOutput()) {
      std::string doseBase = config->GetDoseOutputFilePath();
      G4int doseBufferSize = config->GetDoseBufferSize();
#ifdef G4MULTITHREADED
      if (G4Threading::IsWorkerThread()) {
        fThreadDoseBuffer = new DoseBuffer(doseBufferSize);
      } else {
        // Remove existing file (if any) and create new one
        std::string dosePath = doseBase + ".dose";
        if (std::remove(dosePath.c_str()) != 0 && errno != ENOENT) {
          // ENOENT means file doesn't exist, which is fine
          // Other errors might indicate permission issues or file in use
          G4cerr << "WARNING: Cannot remove existing dose file: " << dosePath << G4endl;
          G4cerr << "         Error: " << std::strerror(errno) << G4endl;
          G4cerr << "         Will attempt to truncate instead..." << G4endl;
        }
        std::ofstream truncateDose(dosePath, std::ios::out | std::ios::trunc | std::ios::binary);
        if (!truncateDose.good()) {
          G4cerr << "ERROR: Cannot create dose output file: " << dosePath << G4endl;
          G4cerr << "       Error: " << std::strerror(errno) << G4endl;
          G4cerr << "       Please check file permissions and ensure no other process is using it." << G4endl;
          return;
        }
        truncateDose.close();
        if (fMasterDoseBuffer == nullptr) {
          fMasterDoseBuffer = new DoseBuffer(doseBufferSize);
          fMasterDoseBuffer->SetOutputPath(dosePath);
        }
      }
#else
      // Remove existing file (if any) and create new one
      std::string dosePath = doseBase + ".dose";
      if (std::remove(dosePath.c_str()) != 0 && errno != ENOENT) {
        // ENOENT means file doesn't exist, which is fine
        // Other errors might indicate permission issues or file in use
        G4cerr << "WARNING: Cannot remove existing dose file: " << dosePath << G4endl;
        G4cerr << "         Error: " << std::strerror(errno) << G4endl;
        G4cerr << "         Will attempt to truncate instead..." << G4endl;
      }
      std::ofstream truncateDose(dosePath, std::ios::out | std::ios::trunc | std::ios::binary);
      if (!truncateDose.good()) {
        G4cerr << "ERROR: Cannot create dose output file: " << dosePath << G4endl;
        G4cerr << "       Error: " << std::strerror(errno) << G4endl;
        G4cerr << "       Please check file permissions and ensure no other process is using it." << G4endl;
        return;
      }
      truncateDose.close();
      if (fMasterDoseBuffer == nullptr) {
        fMasterDoseBuffer = new DoseBuffer(doseBufferSize);
        fMasterDoseBuffer->SetOutputPath(dosePath);
      }
#endif
    }
  } else {
    if (config->GetEnableDoseOutput()) {
#ifdef G4MULTITHREADED
      if (G4Threading::IsMasterThread())
#endif
      G4cout << "Dose output is enabled but output_format is csv; dose output is only supported in binary mode and will be ignored." << G4endl;
    }
    G4int threadID = G4Threading::G4GetThreadId();
    std::ostringstream oss;
    oss << outputFilePath << ".thread_" << threadID;
    std::string threadFilePath = oss.str();

    fThreadOutputStream.open(threadFilePath, std::ios::out);
    if (!fThreadOutputStream.is_open()) {
      G4cerr << "ERROR: Cannot open thread output file: " << threadFilePath << G4endl;
      return;
    }
    WriteCSVHeader(fThreadOutputStream);
  }
}

void RunAction::EndOfRunAction(const G4Run* run)
{
  if (fOutputFormat == "binary") {
#ifdef G4MULTITHREADED
    if (G4Threading::IsWorkerThread()) {
      if (fThreadBuffer != nullptr && fThreadBuffer->GetBufferEntries() > 0 && fMasterBuffer != nullptr) {
        fMasterBuffer->AbsorbWorkerBuffer(fThreadBuffer);
      }
      if (fThreadDoseBuffer != nullptr && fThreadDoseBuffer->GetBufferEntries() > 0 && fMasterDoseBuffer != nullptr) {
        fMasterDoseBuffer->AbsorbWorkerBuffer(fThreadDoseBuffer);
      }
    } else {
      if (fMasterBuffer != nullptr && fMasterBuffer->GetBufferEntries() > 0) {
        fMasterBuffer->WriteBuffer(fOutputBasePath + ".phsp");
        fMasterBuffer->ClearBuffer();
      }
      WriteBinaryHeader(fOutputBasePath + ".header");
      G4cout << "\nBinary output complete: " << fOutputBasePath << ".phsp" << G4endl;
      G4cout << "Header file: " << fOutputBasePath << ".header" << G4endl;

      if (fMasterDoseBuffer != nullptr && fMasterDoseBuffer->GetBufferEntries() > 0) {
        Config* config = Config::GetInstance();
        std::string doseBase = config->GetDoseOutputFilePath();
        fMasterDoseBuffer->WriteBuffer(doseBase + ".dose");
        fMasterDoseBuffer->ClearBuffer();
        WriteDoseHeader(doseBase + ".dose.header");
        G4cout << "Dose output: " << doseBase << ".dose" << G4endl;
      }
    }
#else
    if (fMasterBuffer != nullptr && fMasterBuffer->GetBufferEntries() > 0) {
      fMasterBuffer->WriteBuffer(fOutputBasePath + ".phsp");
      fMasterBuffer->ClearBuffer();
    }
    WriteBinaryHeader(fOutputBasePath + ".header");
    if (fMasterDoseBuffer != nullptr && fMasterDoseBuffer->GetBufferEntries() > 0) {
      Config* config = Config::GetInstance();
      std::string doseBase = config->GetDoseOutputFilePath();
      fMasterDoseBuffer->WriteBuffer(doseBase + ".dose");
      fMasterDoseBuffer->ClearBuffer();
      WriteDoseHeader(doseBase + ".dose.header");
      G4cout << "Dose output: " << doseBase << ".dose" << G4endl;
    }
#endif
  } else {
    // ===== CSV output mode =====
    // Close thread-local output file
    if (fThreadOutputStream.is_open()) {
      fThreadOutputStream.flush();
      fThreadOutputStream.close();
    }
    
    // Only master thread merges files
    if (G4Threading::IsMasterThread()) {
      MergeCSVThreadFiles();
    }
  }
  
  // 记录结束时间和CPU时间
  fEndTime = std::chrono::high_resolution_clock::now();
  getrusage(RUSAGE_SELF, &fEndUsage);
  
  // Only master thread outputs statistics
  if (!G4Threading::IsMasterThread()) {
    return;
  }
  
  // 获取墙钟时间
  auto wallDuration = std::chrono::duration_cast<std::chrono::seconds>(fEndTime - fStartTime);
  G4int wallSeconds = wallDuration.count();
  G4int wallHours = wallSeconds / 3600;
  G4int wallMinutes = (wallSeconds % 3600) / 60;
  G4int wallSecs = wallSeconds % 60;
  
  // 计算真实CPU时间（用户时间 + 系统时间）
  long userSeconds = fEndUsage.ru_utime.tv_sec - fStartUsage.ru_utime.tv_sec;
  long userMicros = fEndUsage.ru_utime.tv_usec - fStartUsage.ru_utime.tv_usec;
  if (userMicros < 0) {
    userSeconds--;
    userMicros += 1000000;
  }
  long sysSeconds = fEndUsage.ru_stime.tv_sec - fStartUsage.ru_stime.tv_sec;
  long sysMicros = fEndUsage.ru_stime.tv_usec - fStartUsage.ru_stime.tv_usec;
  if (sysMicros < 0) {
    sysSeconds--;
    sysMicros += 1000000;
  }
  long totalCpuSeconds = userSeconds + sysSeconds;
  long totalCpuMicros = userMicros + sysMicros;
  if (totalCpuMicros >= 1000000) {
    totalCpuSeconds++;
    totalCpuMicros -= 1000000;
  }
  
  G4int cpuHours = totalCpuSeconds / 3600;
  G4int cpuMinutes = (totalCpuSeconds % 3600) / 60;
  G4int cpuSecs = totalCpuSeconds % 60;
  
  // 获取事件数
  G4int numEvents = run->GetNumberOfEvent();
  
  // 输出统计信息
  G4cout << G4endl;
  G4cout << "======================================" << G4endl;
  G4cout << "          Run Statistics            " << G4endl;
  G4cout << "======================================" << G4endl;
  G4cout << "Total events: " << numEvents << G4endl;
  G4cout << "Total Cherenkov photons: " << EventAction::GetTotalPhotonCount() << G4endl;
  G4cout << "Wall clock time: "
         << std::setfill('0')
         << std::setw(2) << wallHours << " h "
         << std::setw(2) << wallMinutes << " m "
         << std::setw(2) << wallSecs << " s" << G4endl;
  G4cout << "CPU time: "
         << std::setfill('0')
         << std::setw(2) << cpuHours << " h "
         << std::setw(2) << cpuMinutes << " m "
         << std::setw(2) << cpuSecs << " s" << G4endl;
  
  // Always show performance metrics
  G4double eventsPerSecond = (wallSeconds > 0) ? (G4double)numEvents / wallSeconds : 0.0;
  G4double photonsPerEvent = (numEvents > 0) ? (G4double)EventAction::GetTotalPhotonCount() / numEvents : 0.0;
  G4double speedup = (wallSeconds > 0) ? (G4double)totalCpuSeconds / wallSeconds : 0.0;
  G4cout << "Events/sec (wall): " << std::fixed << std::setprecision(1) << eventsPerSecond << G4endl;
  G4cout << "Avg photons/event: " << std::fixed << std::setprecision(1) << photonsPerEvent << G4endl;
  if (wallSeconds > 0) {
    G4cout << "Speedup (CPU/Wall): " << std::fixed << std::setprecision(1) << speedup << "x" << G4endl;
  }
  
  G4cout << "======================================" << G4endl;
  G4cout << G4endl;

  // 写出本次 Run 的元数据 JSON，便于后处理和追踪
  // 元数据文件路径：与 .phsp/.header 同目录，名为 "<base>.run_meta.json"
  long cpuSecondsLong = totalCpuSeconds;  // 已是 long
#ifdef G4MULTITHREADED
  int nThreads = G4MTRunManager::GetMasterRunManager()->GetNumberOfThreads();
#else
  int nThreads = 1;
#endif
  long totalDeposits = 0;
  std::string doseOutputBasePath = "";
  if (fMasterDoseBuffer != nullptr) {
    totalDeposits = fMasterDoseBuffer->GetTotalEntries();
    Config* cfg = Config::GetInstance();
    if (cfg && cfg->GetEnableDoseOutput()) {
      doseOutputBasePath = cfg->GetDoseOutputFilePath();
    }
  }
  RunMetadata::Write(
    fOutputBasePath + ".run_meta.json",
    run,
    fOutputBasePath,
    fOutputFormat,
    wallSeconds,
    cpuSecondsLong,
    static_cast<long>(EventAction::GetTotalPhotonCount()),
    nThreads,
    totalDeposits,
    doseOutputBasePath,
    static_cast<long>(EventAction::GetDoseDepositsWithoutPrimary())
  );
}

void RunAction::RecordPhotonData(G4double initX, G4double initY, G4double initZ,
                                 G4double initDirX, G4double initDirY, G4double initDirZ,
                                 G4double finalX, G4double finalY, G4double finalZ,
                                 G4double finalDirX, G4double finalDirY, G4double finalDirZ,
                                 G4double finalEnergy)
{
  if (fOutputFormat == "binary") {
    // ===== Binary output mode with buffer =====
#ifdef G4MULTITHREADED
    PhotonBuffer* buffer = G4Threading::IsWorkerThread() ? fThreadBuffer : fMasterBuffer;
#else
    PhotonBuffer* buffer = fMasterBuffer;
#endif
    
    if (buffer == nullptr) return;
    
    // Fill buffer
    buffer->Fill(initX, initY, initZ, initDirX, initDirY, initDirZ,
                 finalX, finalY, finalZ, finalDirX, finalDirY, finalDirZ,
                 finalEnergy);
    
    // Check if buffer is full
    if (buffer->IsBufferFull()) {
#ifdef G4MULTITHREADED
      if (G4Threading::IsWorkerThread()) {
        // Worker buffer full: absorb to master buffer
        if (fMasterBuffer != nullptr) {
          fMasterBuffer->AbsorbWorkerBuffer(buffer);
        }
      } else {
        // Master buffer full: write to disk
        buffer->WriteBuffer(fOutputBasePath + ".phsp");
        buffer->ClearBuffer();
      }
#else
      // Sequential mode: write to disk
      buffer->WriteBuffer(fOutputBasePath + ".phsp");
      buffer->ClearBuffer();
#endif
    }
    
  } else {
    // ===== CSV output mode =====
    if (!fThreadOutputStream.is_open()) return;
    
    // Calculate energy (convert MeV to micro-eV)
    G4double energyInMicroeV = (finalEnergy / eV) * 1000000.0;
    
    // Write to thread-local file - no locking needed!
    fThreadOutputStream << std::scientific << std::setprecision(6)
                        << (initX/cm) << "," << (initY/cm) << "," << (initZ/cm) << ","
                        << initDirX << "," << initDirY << "," << initDirZ << ","
                        << (finalX/cm) << "," << (finalY/cm) << "," << (finalZ/cm) << ","
                        << finalDirX << "," << finalDirY << "," << finalDirZ << ","
                        << energyInMicroeV << "\n";
  }
}

// Helper method: Write CSV header
void RunAction::WriteCSVHeader(std::ofstream& out)
{
  out << "InitialX,InitialY,InitialZ,"
      << "InitialDirX,InitialDirY,InitialDirZ,"
      << "FinalX,FinalY,FinalZ,"
      << "FinalDirX,FinalDirY,FinalDirZ,"
      << "FinalEnergyMicroeV\n";
}

// Helper method: Merge CSV thread files
void RunAction::MergeCSVThreadFiles()
{
  G4cout << "\nMerging thread output files..." << G4endl;
  std::ofstream finalOutput(fOutputBasePath, std::ios::out);
  if (!finalOutput.is_open()) {
    G4cerr << "ERROR: Cannot create final output file: " << fOutputBasePath << G4endl;
    return;
  }
  
  // Write header once
  WriteCSVHeader(finalOutput);
  
  // Merge all thread files (MT: GetNumberOfThreads; sequential: 1 file .thread_0)
#ifdef G4MULTITHREADED
  G4int numThreads = G4MTRunManager::GetMasterRunManager()->GetNumberOfThreads();
#else
  G4int numThreads = 1;
#endif
  for (G4int i = 0; i < numThreads; i++) {
    std::ostringstream oss;
    oss << fOutputBasePath << ".thread_" << i;
    std::string threadFilePath = oss.str();
    
    std::ifstream threadFile(threadFilePath, std::ios::in);
    if (!threadFile.is_open()) {
      G4cerr << "WARNING: Cannot open thread file: " << threadFilePath << G4endl;
      continue;
    }
    
    // Skip header line in thread file
    std::string headerLine;
    std::getline(threadFile, headerLine);
    
    // Copy all data lines
    std::string line;
    while (std::getline(threadFile, line)) {
      finalOutput << line << "\n";
    }
    
    threadFile.close();
    
    // Delete thread file after merging
    std::remove(threadFilePath.c_str());
  }
  
  finalOutput.close();
  G4cout << "Merge complete: " << fOutputBasePath << G4endl;
}

// Helper method: Write binary header file
void RunAction::WriteBinaryHeader(const std::string& headerPath)
{
  std::ofstream headerFile(headerPath, std::ios::out);
  if (!headerFile.is_open()) {
    G4cerr << "WARNING: Cannot create header file: " << headerPath << G4endl;
    return;
  }
  
  headerFile << "Binary Phase Space File\n";
  headerFile << "========================\n\n";
  headerFile << "Format: Binary (little-endian)\n";
  headerFile << "Data type: float32 (4 bytes per value)\n";
  headerFile << "Total fields per photon: 13\n";
  headerFile << "Bytes per photon: 52\n\n";
  
  headerFile << "Field order:\n";
  headerFile << "  1. InitialX [cm] (f4)\n";
  headerFile << "  2. InitialY [cm] (f4)\n";
  headerFile << "  3. InitialZ [cm] (f4)\n";
  headerFile << "  4. InitialDirX (f4)\n";
  headerFile << "  5. InitialDirY (f4)\n";
  headerFile << "  6. InitialDirZ (f4)\n";
  headerFile << "  7. FinalX [cm] (f4)\n";
  headerFile << "  8. FinalY [cm] (f4)\n";
  headerFile << "  9. FinalZ [cm] (f4)\n";
  headerFile << " 10. FinalDirX (f4)\n";
  headerFile << " 11. FinalDirY (f4)\n";
  headerFile << " 12. FinalDirZ (f4)\n";
  headerFile << " 13. FinalEnergy [microeV] (f4)\n\n";
  
  headerFile << "Python reading example:\n";
  headerFile << "  import numpy as np\n";
  headerFile << "  data = np.fromfile('file.phsp', dtype='float32')\n";
  headerFile << "  data = data.reshape(-1, 13)\n";
  headerFile << "  # Access: data[:, 0] = InitialX, data[:, 12] = Energy\n";

  headerFile.close();
}

void RunAction::RecordDoseData(G4double x, G4double y, G4double z,
                               G4double dx, G4double dy, G4double dz,
                               G4double energy, G4int event_id, G4int pdg)
{
  Config* config = Config::GetInstance();
  if (!config->GetEnableDoseOutput() || fOutputFormat != "binary") return;
#ifdef G4MULTITHREADED
  DoseBuffer* buffer = G4Threading::IsWorkerThread() ? fThreadDoseBuffer : fMasterDoseBuffer;
#else
  DoseBuffer* buffer = fMasterDoseBuffer;
#endif
  if (buffer == nullptr) return;

  buffer->Fill(x, y, z, dx, dy, dz, energy, event_id, pdg);

  if (buffer->IsBufferFull()) {
    std::string doseBase = config->GetDoseOutputFilePath();
    std::string dosePath = doseBase + ".dose";
#ifdef G4MULTITHREADED
    if (G4Threading::IsWorkerThread()) {
      if (fMasterDoseBuffer != nullptr) {
        fMasterDoseBuffer->AbsorbWorkerBuffer(buffer);
      }
    } else {
      buffer->WriteBuffer(dosePath);
      buffer->ClearBuffer();
    }
#else
    buffer->WriteBuffer(dosePath);
    buffer->ClearBuffer();
#endif
  }
}

void RunAction::WriteDoseHeader(const std::string& headerPath)
{
  std::ofstream headerFile(headerPath, std::ios::out);
  if (!headerFile.is_open()) {
    G4cerr << "WARNING: Cannot create dose header file: " << headerPath << G4endl;
    return;
  }
  headerFile << "Dose raw energy deposit binary\n";
  headerFile << "==============================\n\n";
  headerFile << "Format: Binary (little-endian)\n";
  headerFile << "Bytes per record: 36\n";
  headerFile << "Fields per record: 9\n\n";
  headerFile << "Field order:\n";
  headerFile << "  1. x [cm] (float32)\n";
  headerFile << "  2. y [cm] (float32)\n";
  headerFile << "  3. z [cm] (float32)\n";
  headerFile << "  4. dx [cm] relative to primary vertex (float32)\n";
  headerFile << "  5. dy [cm] (float32)\n";
  headerFile << "  6. dz [cm] (float32)\n";
  headerFile << "  7. energy [MeV] (float32)\n";
  headerFile << "  8. event_id (uint32)\n";
  headerFile << "  9. pdg (int32)\n\n";
  headerFile << "When event has no primary vertex, dx=dy=dz=0; see run_meta dose_deposits_without_primary.\n\n";
  headerFile << "Python reading example:\n";
  headerFile << "  import numpy as np\n";
  headerFile << "  dt = np.dtype([('x','f4'),('y','f4'),('z','f4'),('dx','f4'),('dy','f4'),('dz','f4'),('energy','f4'),('event_id','u4'),('pdg','i4')])\n";
  headerFile << "  data = np.fromfile('file.dose', dtype=dt)\n";
  headerFile.close();
}
