//
// PhotonBuffer.hh - Buffer management for binary output
// Similar to TOPAS TsVNtuple buffer system
//

#ifndef PhotonBuffer_h
#define PhotonBuffer_h 1

#include "globals.hh"
#include <cstdint>
#include <vector>
#include <string>
#include <fstream>

#ifdef G4MULTITHREADED
#include "G4AutoLock.hh"
#endif

// Structure to hold single photon data for binary output (v2, 60 bytes)
struct BinaryPhotonData {
    float initX, initY, initZ;          // Initial position (cm)
    float initDirX, initDirY, initDirZ; // Initial direction (unit vector)
    float finalX, finalY, finalZ;       // Final position (cm)
    float finalDirX, finalDirY, finalDirZ; // Final direction (unit vector)
    float finalEnergy;                  // Final energy (microeV)
    uint32_t event_id;                  // G4Event::GetEventID()
    int32_t track_id;                   // G4Track::GetTrackID(); -1 = unknown/invalid
};
static_assert(sizeof(BinaryPhotonData) == 60, "BinaryPhotonData must be 60 bytes for format v2");

class PhotonBuffer
{
public:
    PhotonBuffer(G4int bufferSize = 10000);
    ~PhotonBuffer();
    
    // Add photon data to buffer
    void Fill(G4double initX, G4double initY, G4double initZ,
              G4double initDirX, G4double initDirY, G4double initDirZ,
              G4double finalX, G4double finalY, G4double finalZ,
              G4double finalDirX, G4double finalDirY, G4double finalDirZ,
              G4double finalEnergy, G4int event_id, G4int track_id);
    
    // Write buffer to binary file
    void WriteBuffer(const std::string& filePath);
    
    // Set output path for automatic flush
    void SetOutputPath(const std::string& filePath) { fOutputPath = filePath; }
    
    // Absorb data from worker buffer (for master thread)
    void AbsorbWorkerBuffer(PhotonBuffer* workerBuffer);
    
    // Clear buffer
    void ClearBuffer();
    
    // Get statistics
    G4int GetBufferEntries() const { return fBufferEntries; }
    G4long GetTotalEntries() const { return fTotalEntries; }
    G4int GetBufferSize() const { return fBufferSize; }
    
    // Check if buffer is full
    G4bool IsBufferFull() const { return fBufferEntries >= fBufferSize; }
    
private:
    std::vector<BinaryPhotonData> fBuffer;
    G4int fBufferSize;
    G4int fBufferEntries;
    G4long fTotalEntries;
    std::string fOutputPath;  // Output file path for auto-flush
    
#ifdef G4MULTITHREADED
    static G4Mutex fBufferMutex;
#endif
};

#endif
