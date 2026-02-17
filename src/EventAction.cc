//
// EventAction.cc
//

#include "EventAction.hh"
#include "RunAction.hh"

#include "G4Event.hh"
#include "G4RunManager.hh"
#include "G4SystemOfUnits.hh"

// 初始化静态成员变量
G4int EventAction::fTotalPhotonCount = 0;

EventAction::EventAction(RunAction* runAction)
: G4UserEventAction(),
  fRunAction(runAction)
{}

EventAction::~EventAction()
{}

void EventAction::BeginOfEventAction(const G4Event*)
{    
  // Clear the photon data map at the beginning of each event
  fPhotonDataMap.clear();
}

void EventAction::EndOfEventAction(const G4Event*)
{   
  // Write out all complete photon data
  for (const auto& pair : fPhotonDataMap) {
    const PhotonData& data = pair.second;
    if (data.hasData) {
      fRunAction->RecordPhotonData(
        data.initialX, data.initialY, data.initialZ,
        data.initialDirX, data.initialDirY, data.initialDirZ,
        data.finalX, data.finalY, data.finalZ,
        data.finalDirX, data.finalDirY, data.finalDirZ,
        data.finalEnergy
      );
    }
  }
}

void EventAction::RecordPhotonCreation(G4int trackID, G4double x, G4double y, G4double z,
                                       G4double dirx, G4double diry, G4double dirz)
{
  fTotalPhotonCount++;  // 递增光子计数
  
  PhotonData& data = fPhotonDataMap[trackID];
  data.initialX = x;
  data.initialY = y;
  data.initialZ = z;
  data.initialDirX = dirx;
  data.initialDirY = diry;
  data.initialDirZ = dirz;
  data.hasData = false;
}

void EventAction::RecordPhotonEnd(G4int trackID, G4double x, G4double y, G4double z,
                                  G4double dirx, G4double diry, G4double dirz, G4double energy)
{
  auto it = fPhotonDataMap.find(trackID);
  if (it != fPhotonDataMap.end()) {
    PhotonData& data = it->second;
    data.finalX = x;
    data.finalY = y;
    data.finalZ = z;
    data.finalDirX = dirx;
    data.finalDirY = diry;
    data.finalDirZ = dirz;
    data.finalEnergy = energy;
    data.hasData = true;
  }
}
