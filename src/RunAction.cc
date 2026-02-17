//
// RunAction.cc
//

#include "RunAction.hh"
#include "EventAction.hh"

#include "G4Run.hh"
#include "G4RunManager.hh"
#include "G4SystemOfUnits.hh"
#include "G4Threading.hh"
#include "Config.hh"
#include <iostream>
#include <iomanip>
#include <sstream>
#include <fstream>
#include <algorithm>

// Define static class members
thread_local std::ofstream RunAction::fThreadOutputStream;
std::string RunAction::fOutputBasePath = "";
thread_local PhotonBuffer* RunAction::fThreadBuffer = nullptr;
PhotonBuffer* RunAction::fMasterBuffer = nullptr;

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
}

void RunAction::BeginOfRunAction(const G4Run*)
{ 
  // 记录开始时间和CPU时间
  fStartTime = std::chrono::high_resolution_clock::now();
  getrusage(RUSAGE_SELF, &fStartUsage);
  
  // 重置光子计数
  EventAction::ResetPhotonCount();
  
  // Get output config
  Config* config = Config::GetInstance();
  std::string outputFilePath = config->GetOutputFilePath();
  fOutputBasePath = outputFilePath;
  fOutputFormat = config->GetOutputFormat();
  
  // Convert output format to lowercase for comparison
  std::transform(fOutputFormat.begin(), fOutputFormat.end(), fOutputFormat.begin(), ::tolower);
  
  G4cout << "Output format: " << fOutputFormat << G4endl;
  
  if (fOutputFormat == "binary") {
    // ===== Binary output mode with buffer =====
    G4int bufferSize = config->GetBufferSize();
    
#ifdef G4MULTITHREADED
    if (G4Threading::IsWorkerThread()) {
      // Worker thread: create thread-local buffer
      fThreadBuffer = new PhotonBuffer(bufferSize);
      G4cout << "Worker thread " << G4Threading::G4GetThreadId() 
             << " buffer size: " << fThreadBuffer->GetBufferSize() << G4endl;
    } else {
      // Master thread: create master buffer
      if (fMasterBuffer == nullptr) {
        fMasterBuffer = new PhotonBuffer(bufferSize);
        fMasterBuffer->SetOutputPath(fOutputBasePath + ".phsp");  // Set path for auto-flush
        G4cout << "Master buffer created with size: " << bufferSize << G4endl;
      }
    }
#else
    // Sequential mode: single buffer
    if (fMasterBuffer == nullptr) {
      fMasterBuffer = new PhotonBuffer(bufferSize);
      fMasterBuffer->SetOutputPath(fOutputBasePath + ".phsp");  // Set path for auto-flush
    }
#endif
    
  } else {
    // ===== CSV output mode with thread-local files =====
    G4int threadID = G4Threading::G4GetThreadId();
    std::ostringstream oss;
    oss << outputFilePath << ".thread_" << threadID;
    std::string threadFilePath = oss.str();
    
    fThreadOutputStream.open(threadFilePath, std::ios::out);
    if (!fThreadOutputStream.is_open()) {
      G4cerr << "ERROR: Cannot open thread output file: " << threadFilePath << G4endl;
      return;
    }
    
    // Write CSV header
    WriteCSVHeader(fThreadOutputStream);
  }
}

void RunAction::EndOfRunAction(const G4Run* run)
{
  if (fOutputFormat == "binary") {
    // ===== Binary output mode =====
#ifdef G4MULTITHREADED
    if (G4Threading::IsWorkerThread()) {
      // Worker thread: flush remaining buffer to master
      if (fThreadBuffer != nullptr && fThreadBuffer->GetBufferEntries() > 0) {
        if (fMasterBuffer != nullptr) {
          fMasterBuffer->AbsorbWorkerBuffer(fThreadBuffer);
        }
      }
    } else {
      // Master thread: write remaining buffer to disk
      if (fMasterBuffer != nullptr && fMasterBuffer->GetBufferEntries() > 0) {
        fMasterBuffer->WriteBuffer(fOutputBasePath + ".phsp");
        fMasterBuffer->ClearBuffer();
      }
      
      // Write binary header file
      WriteBinaryHeader(fOutputBasePath + ".header");
      
      G4cout << "\nBinary output complete: " << fOutputBasePath << ".phsp" << G4endl;
      G4cout << "Header file: " << fOutputBasePath << ".header" << G4endl;
    }
#else
    // Sequential mode
    if (fMasterBuffer != nullptr && fMasterBuffer->GetBufferEntries() > 0) {
      fMasterBuffer->WriteBuffer(fOutputBasePath + ".phsp");
      fMasterBuffer->ClearBuffer();
    }
    WriteBinaryHeader(fOutputBasePath + ".header");
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
  
  // Merge all thread files
  G4int numThreads = G4Threading::GetNumberOfRunningWorkerThreads();
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
