//
// PhotonBuffer.cc - Implementation of buffer management
// Similar to TOPAS TsVNtuple buffer system
//

#include "PhotonBuffer.hh"
#include "G4SystemOfUnits.hh"
#include "G4Threading.hh"
#include <fstream>
#include <iostream>

#ifdef G4MULTITHREADED
#include "G4MTRunManager.hh"
G4Mutex PhotonBuffer::fBufferMutex = G4MUTEX_INITIALIZER;
#endif

PhotonBuffer::PhotonBuffer(G4int bufferSize)
: fBufferSize(bufferSize), fBufferEntries(0), fTotalEntries(0), fOutputPath("")
{
#ifdef G4MULTITHREADED
    // Adjust buffer size per worker thread (TOPAS 风格: 使用 GetNumberOfThreads)
    if (G4Threading::IsWorkerThread()) {
        G4int nThreads = G4MTRunManager::GetMasterRunManager()->GetNumberOfThreads();
        if (nThreads > 0) {
            fBufferSize = bufferSize / nThreads;
        }
    }
#endif
    
    fBuffer.reserve(fBufferSize);
}

PhotonBuffer::~PhotonBuffer()
{
    ClearBuffer();
}

void PhotonBuffer::Fill(G4double initX, G4double initY, G4double initZ,
                        G4double initDirX, G4double initDirY, G4double initDirZ,
                        G4double finalX, G4double finalY, G4double finalZ,
                        G4double finalDirX, G4double finalDirY, G4double finalDirZ,
                        G4double finalEnergy, G4int event_id, G4int track_id)
{
    BinaryPhotonData data;
    
    // Convert to float and store in cm
    data.initX = static_cast<float>(initX / cm);
    data.initY = static_cast<float>(initY / cm);
    data.initZ = static_cast<float>(initZ / cm);
    
    data.initDirX = static_cast<float>(initDirX);
    data.initDirY = static_cast<float>(initDirY);
    data.initDirZ = static_cast<float>(initDirZ);
    
    data.finalX = static_cast<float>(finalX / cm);
    data.finalY = static_cast<float>(finalY / cm);
    data.finalZ = static_cast<float>(finalZ / cm);
    
    data.finalDirX = static_cast<float>(finalDirX);
    data.finalDirY = static_cast<float>(finalDirY);
    data.finalDirZ = static_cast<float>(finalDirZ);
    
    // Convert to microeV
    data.finalEnergy = static_cast<float>((finalEnergy / eV) * 1000000.0);
    
    data.event_id = static_cast<uint32_t>(event_id >= 0 ? event_id : 0);
    data.track_id = static_cast<int32_t>(track_id);
    
    fBuffer.push_back(data);
    fBufferEntries++;
    fTotalEntries++;
}

void PhotonBuffer::WriteBuffer(const std::string& filePath)
{
    if (fBufferEntries == 0) return;
    
    std::ofstream outFile(filePath, std::ios::app | std::ios::binary);
    if (!outFile.good()) {
        G4cerr << "ERROR: Cannot open output file for writing: " << filePath << G4endl;
        return;
    }
    
    // Write all photon data in buffer (60 bytes per photon, v2)
    for (const auto& photon : fBuffer) {
        outFile.write(reinterpret_cast<const char*>(&photon), sizeof(BinaryPhotonData));
    }
    
    outFile.close();
    
    // 不打印每次写入，避免 14 亿光子时刷屏（约 1400 次）
    // G4cout << "Wrote " << fBufferEntries << " photons to " << filePath << G4endl;
}

void PhotonBuffer::AbsorbWorkerBuffer(PhotonBuffer* workerBuffer)
{
#ifdef G4MULTITHREADED
    G4AutoLock lock(&fBufferMutex);
#endif
    
    if (workerBuffer->GetBufferEntries() == 0) return;
    
    // If master buffer cannot accommodate worker buffer, write to disk first
    if (fBufferEntries + workerBuffer->GetBufferEntries() > fBufferSize) {
        if (fBufferEntries > 0) {
            // 不打印每次 flush，避免 MT 下大量 worker 吸收时刷屏
            // G4cout << "Master buffer full, writing " << fBufferEntries << " photons to disk before absorbing worker buffer" << G4endl;
            WriteBuffer(fOutputPath);
            ClearBuffer();
        }
    }
    
    // Absorb worker buffer data
    for (const auto& photon : workerBuffer->fBuffer) {
        fBuffer.push_back(photon);
    }
    
    fBufferEntries += workerBuffer->GetBufferEntries();
    fTotalEntries += workerBuffer->GetBufferEntries();
    
    // Clear worker buffer
    workerBuffer->ClearBuffer();
}

void PhotonBuffer::ClearBuffer()
{
    fBuffer.clear();
    fBufferEntries = 0;
}
