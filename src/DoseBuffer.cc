//
// DoseBuffer.cc - Implementation for dose binary output
//

#include "DoseBuffer.hh"
#include "G4SystemOfUnits.hh"
#include "G4Threading.hh"
#include <fstream>
#include <iostream>

#ifdef G4MULTITHREADED
#include "G4MTRunManager.hh"
G4Mutex DoseBuffer::fBufferMutex = G4MUTEX_INITIALIZER;
#endif

DoseBuffer::DoseBuffer(G4int bufferSize)
: fBufferSize(bufferSize), fBufferEntries(0), fTotalEntries(0), fOutputPath("")
{
#ifdef G4MULTITHREADED
  if (G4Threading::IsWorkerThread()) {
    G4int nThreads = G4MTRunManager::GetMasterRunManager()->GetNumberOfThreads();
    if (nThreads > 0) {
      fBufferSize = bufferSize / nThreads;
    }
  }
#endif

  fBuffer.reserve(fBufferSize);
}

DoseBuffer::~DoseBuffer()
{
  ClearBuffer();
}

void DoseBuffer::Fill(G4double x, G4double y, G4double z,
                      G4double dx, G4double dy, G4double dz,
                      G4double energy, G4int event_id, G4int pdg)
{
  BinaryDoseData data;
  // x,y,z and dx,dy,dz are already in cm from RunAction/EventAction
  data.x  = static_cast<float>(x);
  data.y  = static_cast<float>(y);
  data.z  = static_cast<float>(z);
  data.dx = static_cast<float>(dx);
  data.dy = static_cast<float>(dy);
  data.dz = static_cast<float>(dz);
  data.energy   = static_cast<float>(energy);
  data.event_id = static_cast<uint32_t>(event_id >= 0 ? event_id : 0);
  data.pdg      = static_cast<int32_t>(pdg);

  fBuffer.push_back(data);
  fBufferEntries++;
  fTotalEntries++;
}

void DoseBuffer::WriteBuffer(const std::string& filePath)
{
  if (fBufferEntries == 0) return;

  std::ofstream outFile(filePath, std::ios::app | std::ios::binary);
  if (!outFile.good()) {
    G4cerr << "ERROR: Cannot open dose output file for writing: " << filePath << G4endl;
    return;
  }

  for (const auto& rec : fBuffer) {
    outFile.write(reinterpret_cast<const char*>(&rec), sizeof(BinaryDoseData));
  }
  outFile.close();
}

void DoseBuffer::AbsorbWorkerBuffer(DoseBuffer* workerBuffer)
{
#ifdef G4MULTITHREADED
  G4AutoLock lock(&fBufferMutex);
#endif

  if (workerBuffer->GetBufferEntries() == 0) return;

  if (fBufferEntries + workerBuffer->GetBufferEntries() > fBufferSize) {
    if (fBufferEntries > 0) {
      WriteBuffer(fOutputPath);
      ClearBuffer();
    }
  }

  for (const auto& rec : workerBuffer->fBuffer) {
    fBuffer.push_back(rec);
  }
  fBufferEntries += workerBuffer->GetBufferEntries();
  fTotalEntries  += workerBuffer->GetBufferEntries();
  workerBuffer->ClearBuffer();
}

void DoseBuffer::ClearBuffer()
{
  fBuffer.clear();
  fBufferEntries = 0;
}
