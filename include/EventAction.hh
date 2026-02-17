//
// EventAction.hh
//

#ifndef EventAction_h
#define EventAction_h 1

#include "G4UserEventAction.hh"
#include "globals.hh"
#include <map>
#include <fstream>
#include <chrono>
#include <atomic>

class RunAction;

struct PhotonData {
  G4double initialX, initialY, initialZ;
  G4double initialDirX, initialDirY, initialDirZ;
  G4double finalX, finalY, finalZ;
  G4double finalDirX, finalDirY, finalDirZ;
  G4double finalEnergy;
  G4bool hasData;
};

class EventAction : public G4UserEventAction
{
  public:
    EventAction(RunAction* runAction);
    virtual ~EventAction();

    virtual void BeginOfEventAction(const G4Event* event);
    virtual void EndOfEventAction(const G4Event* event);

    void RecordPhotonCreation(G4int trackID, G4double x, G4double y, G4double z,
                             G4double dirx, G4double diry, G4double dirz);
    void RecordPhotonEnd(G4int trackID, G4double x, G4double y, G4double z,
                        G4double dirx, G4double diry, G4double dirz, G4double energy);

  private:
    RunAction* fRunAction;
    std::map<G4int, PhotonData> fPhotonDataMap;
    
  public:
    static std::atomic<G4int> fTotalPhotonCount;
    static G4int GetTotalPhotonCount() { return fTotalPhotonCount.load(); }
    static void ResetPhotonCount() { fTotalPhotonCount.store(0); }
};

#endif
