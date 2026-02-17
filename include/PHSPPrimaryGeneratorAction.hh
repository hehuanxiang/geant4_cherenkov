//
// PHSPPrimaryGeneratorAction.hh
// 从Phase Space文件读入粒子
//

#ifndef PHSPPrimaryGeneratorAction_h
#define PHSPPrimaryGeneratorAction_h 1

#include "G4VUserPrimaryGeneratorAction.hh"
#include "G4ParticleGun.hh"
#include "globals.hh"
#include <fstream>
#include <vector>
#include <string>
#include <map>
#ifdef G4MULTITHREADED
#include "G4AutoLock.hh"
#endif

class G4Event;

// 结构体：存储单个粒子信息
struct PHSPParticle {
    G4double posX, posY, posZ;
    G4double dirX, dirY, dirZ;
    G4double energy;
    G4int particleType;
    G4double weight;
};

class PHSPPrimaryGeneratorAction : public G4VUserPrimaryGeneratorAction
{
  public:
    PHSPPrimaryGeneratorAction(const G4String& phspFilePath);    
    virtual ~PHSPPrimaryGeneratorAction();

    void ReadPHSPFile(const G4String& filePath);
    void ReadIAEAPHSPFile(const G4String& filePath, const G4String& headerPath);
    virtual void GeneratePrimaries(G4Event*);
    G4int GetTotalParticles() const { return fPHSPData.size(); }
    G4int GetCurrentParticleIndex() const { return fCurrentParticleIndex; }
    
  private:
    std::vector<PHSPParticle> fPHSPData;  // Local reference to global data
    G4int fCurrentParticleIndex;
    G4bool fCycleData;
    G4ParticleGun* fParticleGun;
    
    G4ParticleDefinition* GetParticleByCode(G4int code);
    void PrintStatistics();
    
    // Static shared PHSP data (loaded once by master thread)
    static std::vector<PHSPParticle> fGlobalPHSPData;
    static G4bool fDataLoaded;
#ifdef G4MULTITHREADED
    static G4Mutex fLoadMutex;
#endif
    
    // Helper function called by master thread only
    void LoadGlobalPHSPData(const G4String& phspFilePath);
};

#endif
