//
// DoseBuffer.hh - Buffer management for dose (raw energy deposit) binary output
// Same pattern as PhotonBuffer: Master/Worker, thread-safe absorb, float32 binary
//

#ifndef DoseBuffer_h
#define DoseBuffer_h 1

#include "globals.hh"
#include <vector>
#include <string>
#include <fstream>
#include <cstdint>

#ifdef G4MULTITHREADED
#include "G4AutoLock.hh"
#endif

// Structure for single dose deposit record (36 bytes, no padding)
struct BinaryDoseData {
  float x, y, z;           // deposition position [cm]
  float dx, dy, dz;        // relative to primary vertex [cm]
  float energy;            // energy deposit [MeV]
  uint32_t event_id;       // event ID (G4Event::GetEventID())
  int32_t pdg;             // particle PDG code
};
static_assert(sizeof(BinaryDoseData) == 36, "BinaryDoseData must be 36 bytes for format compatibility");

class DoseBuffer
{
public:
  DoseBuffer(G4int bufferSize = 10000);
  ~DoseBuffer();

  void Fill(G4double x, G4double y, G4double z,
           G4double dx, G4double dy, G4double dz,
           G4double energy, G4int event_id, G4int pdg);

  void WriteBuffer(const std::string& filePath);
  void SetOutputPath(const std::string& filePath) { fOutputPath = filePath; }
  void AbsorbWorkerBuffer(DoseBuffer* workerBuffer);
  void ClearBuffer();

  G4int GetBufferEntries() const { return fBufferEntries; }
  G4long GetTotalEntries() const { return fTotalEntries; }
  G4int GetBufferSize() const { return fBufferSize; }
  G4bool IsBufferFull() const { return fBufferEntries >= fBufferSize; }

private:
  std::vector<BinaryDoseData> fBuffer;
  G4int fBufferSize;
  G4int fBufferEntries;
  G4long fTotalEntries;
  std::string fOutputPath;

#ifdef G4MULTITHREADED
  static G4Mutex fBufferMutex;
#endif
};

#endif
